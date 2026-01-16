import os
import numpy as np
import torch
import base64
import re  # <--- NUEVO: Para limpiar símbolos
import io
import time
import wave

# --- LIBRERÍAS DE GOOGLE CLOUD ---
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting, Content, Part
from google.cloud import texttospeech

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from faster_whisper import WhisperModel

# ==============================================================================
#  CONFIGURACIÓN
# ==============================================================================
PROJECT_ID = "ulal-cuu"  # <--- CONFIRMA QUE ESTE SEA TU ID REAL
LOCATION = "us-central1"

# Voz: Usamos Fenrir o Puck para hombre, o Neural2-C
GOOGLE_VOICE_NAME = "es-US-Chirp3-HD-Fenrir" 
GOOGLE_VOICE_LANG = "es-US"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
SAMPLE_RATE = 16000
VAD_WINDOW = 512
VAD_PATIENCE = 30 

PRESETS = {
    "intro_1": "Hola, te habla Angel de Universidad ULAL. ¿Con quién tengo el gusto?",
}

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10 * 1024 * 1024)

# ==============================================================================
#  INICIALIZACIÓN
# ==============================================================================
print(f">>> Conectando a Google Cloud Project: {PROJECT_ID}...")
vertexai.init(project=PROJECT_ID, location=LOCATION)
tts_client = texttospeech.TextToSpeechClient()

# ==============================================================================
#  CEREBRO: GEMINI (CON TODO EL CONOCIMIENTO DE ULAL)
# ==============================================================================
SYSTEM_INSTRUCTION = """
ERES: Angel, asesor de admisiones experto de ULAL.
OBJETIVO: Vender consultivamente.
FORMATO DE SALIDA: SOLO TEXTO PLANO. Prohibido usar asteriscos (*), guiones (-), emojis o listas con viñetas. Escribe como si fuera un guion de teatro hablado.

ESTADO ACTUAL:
1. Ya saludaste.
2. El usuario acaba de decir su NOMBRE.

TU GUIÓN OBLIGATORIO (FLUJO PRINCIPAL):

PASO 1: VERIFICACIÓN
- Saluda por su nombre con energía.
- Pitch Rápido: "Vi que pediste info sobre tu bachillerato. ¿Tienes un minuto para explicarte cómo certificarlo en 4 meses?"

PASO 2: EL GANCHO + FILTRO
- Si acepta: "Excelente. El programa tiene validez oficial SEP y es ideal si trabajas. ¿De qué municipio o estado nos contactas?" (Si el alumno menciona alguna ubicacion que no esté en la base de datos, mencionar que estamos creciendo y muy pronto llegaremos a su ciudad, es necesario estar cerca ya que el examen es presencial).

PASO 3: LA OFERTA (PRECIO + BECA)
- Oferta Principal: "Genial, para tu zona tengo una beca del 50%. Tu inscripción baja de 3000 a 1500 pesos. La mensualidad queda en 999 pesos online o 299 semanales presencial."
- Si se le hace caro (AS BAJO LA MANGA): Ofrece el PAGO ÚNICO de $3,499 que cubre TODO el curso (Ahorro total).
- Filtro: "¿Cuentas con certificado de secundaria?"

PASO 4: CIERRE DOBLE
- "Perfecto. Para respetar la beca, necesito generar tu ficha. ¿A qué hora te marco para ayudarte con el registro? Y confírmame tu WhatsApp."

--- BASE DE DATOS (ÚSALA SOLO SI PREGUNTAN) ---

1. COSTOS OCULTOS (Sé transparente si preguntan):
- Examen de Certificación (Prepa): $5,999.52 (Se paga al final).
- Trámite de Certificado: $999.
- Guías de estudio (Obligatorias): $999.
- Licenciaturas: Titulación cuesta $34,999.52.

2. GARANTÍA DE ACREDITACIÓN:
- "Si repruebas, repites el curso GRATIS o te devolvemos tu dinero".
- CONDICIÓN: Debes tener 95% de asistencia y pagos al corriente.

3. REQUISITOS ESPECÍFICOS:
- Prepa: Acta, CURP, Certificado Secundaria, 4 fotos.
- Carreras Reguladas (Derecho, Ing. Industrial, Contabilidad): REQUIEREN certificado de bachillerato Y ADEMÁS tener carrera trunca (50% créditos) O 5 años de experiencia laboral comprobable (Portafolio de evidencias).
- Carreras NO Reguladas (Admin, Merca, Pedagogía): Requieren 21 años + 3 años de experiencia.

4. UBICACIONES PRESENCIALES:
- Chihuahua Capital:
    - Centro: Calle 4ta Julio Ornelas Kuchle #6 Altos Col. Centro.
    - Norte: Av. Industrias #17112 Col. Luis Donaldo Colosio.

- Cd. Cuauhtemoc:
    - Calle Guerrero #65 Col. Centro .

- Delicias:
    - Ave del Parque Pte. # 1408 Altos Col. Del Empleado.

- Parral:
    - Bartolomé De Las Casas #945.

- Tijuana:
    - Instituto Tecnológico de Tijuana 2020 Otay Tecnológico.

REGLA DE ORO:
NO menciones los costos de examen o guías en el primer mensaje. Solo dálos si el cliente pregunta "¿hay otros costos?" o si ya estás en la fase final de cierre y quieres ser transparente. Tu prioridad es la inscripción de $1,500.
"""

model_gemini = GenerativeModel(
    "gemini-2.5-flash-lite", # O usa gemini-1.5-pro-001 si tienes cuota, flash es más rápido
    system_instruction=SYSTEM_INSTRUCTION
)

# --- MODELOS LOCALES ---
print(">>> Cargando Whisper y VAD...")
model_vad, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')
stt_model = WhisperModel("base", device="cuda", compute_type="float16")

session_data = {"buffer": [], "silence_counter": 0, "is_speaking": False, "chat_session": None}

# ==========================================
#  LIMPIEZA DE TEXTO (NUEVO)
# ==========================================
def limpiar_texto_para_tts(texto):
    """Elimina markdown y símbolos que suenan mal en el TTS"""
    # Eliminar asteriscos, guiones bajos, numerales (Markdown)
    texto = re.sub(r'[*_#\-•]', '', texto)
    # Eliminar emojis (Rango básico Unicode)
    texto = re.sub(r'[^\w\s,?.!¡¿$áéíóúÁÉÍÓÚñÑ]', '', texto)
    # Eliminar espacios dobles
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

# ==========================================
#  MOTOR DE AUDIO: GOOGLE CLOUD TTS
# ==========================================
def generar_audio_google(texto):
    try:
        # 1. Limpiamos el texto antes de enviarlo
        texto_limpio = limpiar_texto_para_tts(texto)
        
        synthesis_input = texttospeech.SynthesisInput(text=texto_limpio)
        
        voice = texttospeech.VoiceSelectionParams(
            language_code=GOOGLE_VOICE_LANG,
            name=GOOGLE_VOICE_NAME
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.15, # Un poco más rápido para fluidez
            pitch=0.0
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        return response.audio_content
    except Exception as e:
        print(f"❌ Error Google TTS: {e}")
        return None

def inicializar_sistema():
    if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
    
    for key, txt in PRESETS.items():
        path = os.path.join(CACHE_DIR, f"{key}.mp3")
        if not os.path.exists(path):
            print(f">>> Generando caché: {key}")
            audio = generar_audio_google(txt)
            if audio:
                with open(path, "wb") as f: f.write(audio)

    try:
        dummy = model_gemini.start_chat(history=[])
        dummy.send_message("Warmup")
        print(">>> 🚀 SISTEMA LISTO.")
    except Exception as e:
        print(f"Advertencia Warmup: {e}")

def enviar_preset(key):
    path = os.path.join(CACHE_DIR, f"{key}.mp3")
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
            emit('ai_text', PRESETS[key])
            emit('audio_response', b64)

def enviar_generado(texto):
    # Enviamos el texto ORIGINAL (con formato si hubiera) al chat visual
    emit('ai_text', texto)
    
    # Enviamos el texto LIMPIO al motor de audio
    print(f"🎵 TTS: {texto}")
    audio = generar_audio_google(texto)
    if audio:
        b64 = base64.b64encode(audio).decode('utf-8')
        emit('audio_response', b64)

# ==========================================
#  SOCKETS
# ==========================================
@app.route('/')
def index(): return render_template('index.html')

@socketio.on('start_conversation')
def handle_start():
    global session_data
    history_obj = [
        Content(role="model", parts=[Part.from_text(PRESETS["intro_1"])])
    ]
    session_data["chat_session"] = model_gemini.start_chat(history=history_obj)
    enviar_preset("intro_1")

@socketio.on('audio_stream')
def handle_stream(blob):
    global session_data
    if not isinstance(blob, bytes): return
    audio_full = np.frombuffer(blob, dtype=np.int16).astype(np.float32) / 32768.0
    
    for i in range(0, len(audio_full), VAD_WINDOW):
        chunk = audio_full[i: i + VAD_WINDOW]
        if len(chunk) < VAD_WINDOW: continue
        prob = model_vad(torch.from_numpy(chunk), SAMPLE_RATE).item()
        
        if prob > 0.5:
            session_data["is_speaking"] = True
            session_data["silence_counter"] = 0
            session_data["buffer"].append(chunk)
        elif session_data["is_speaking"]:
            session_data["silence_counter"] += 1
            session_data["buffer"].append(chunk)
            if session_data["silence_counter"] > VAD_PATIENCE: 
                procesar()
                session_data["buffer"] = []
                session_data["silence_counter"] = 0
                session_data["is_speaking"] = False

def procesar():
    global session_data
    full_audio = np.concatenate(session_data["buffer"])
    segs, _ = stt_model.transcribe(full_audio, beam_size=1, language="es")
    texto = "".join([s.text for s in segs]).strip()
    if not texto: return
    
    print(f"Usuario: {texto}")
    emit('user_transcript', texto)

    try:
        response = session_data["chat_session"].send_message(texto, stream=True)
        buffer = ""
        for chunk in response:
            if chunk.text:
                w = chunk.text
                buffer += w
                # Streaming rápido
                if any(c in w for c in [".", "?", "!", "\n"]) and len(buffer) > 10:
                    enviar_generado(buffer)
                    buffer = ""
        if buffer.strip(): enviar_generado(buffer)
    except Exception as e:
        print(f"Error Vertex AI: {e}")

if __name__ == '__main__':
    inicializar_sistema() 
    print(">>> Servidor ONLINE en http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)