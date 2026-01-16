import os
import time
import csv
import subprocess
import sys

# --- CONFIGURACIÓN ---
ADB_ID = "426fbf59"  # Tu cable USB

# Archivos
ARCHIVO_AUDIO_LOCAL = "mensaje.mp3"
ARCHIVO_AUDIO_CEL   = "/sdcard/mensaje.mp3"
ARCHIVO_CSV         = "numeros.csv"

# COORDENADAS ALTAVOZ (Verifica en scrcpy)
BTN_ALTAVOZ_X = 850 
BTN_ALTAVOZ_Y = 1620 

# Duración del audio
DURACION_AUDIO = 20

def adb_cmd(comando):
    """Ejecuta comando ADB simple"""
    os.system(f"adb -s {ADB_ID} shell {comando}")

def preparar_sistema():
    """Sube audio, da permisos y sube volumen"""
    print("📂 Preparando sistema...")
    os.system(f"adb -s {ADB_ID} push {ARCHIVO_AUDIO_LOCAL} {ARCHIVO_AUDIO_CEL}")
    adb_cmd(f"chmod 777 {ARCHIVO_AUDIO_CEL}") # Permisos totales para que cualquier app lo lea
    
    # Pre-cargar volumen por si acaso
    for _ in range(5):
        adb_cmd("input keyevent 24") 

def esperar_contestacion_logcat_radio(timeout=60):
    """
    Estrategia 'Caramelo' (Logcat) adaptada a Linux.
    Usamos '-b radio' para filtrar solo eventos de telefonía.
    Busca el cambio exacto de estado a 'CALL_STATE_OFFHOOK' o 'ACTIVE'.
    """
    print(f"   ⏳ Esperando contestación (Logcat Radio)...")
    
    # 1. Limpiamos buffer antiguo
    os.system(f"adb -s {ADB_ID} logcat -c")

    # 2. Leemos SOLO el buffer de radio (telephony) que es más limpio
    cmd = ["adb", "-s", ADB_ID, "logcat", "-b", "radio", "-v", "time"]
    
    # stdout=subprocess.PIPE es necesario para leer en tiempo real
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    start_time = time.time()
    conectado = False

    while (time.time() - start_time) < timeout:
        # Leemos línea por línea (bloqueante, igual que en tu script de Windows)
        line = process.stdout.readline()
        if not line: continue
        
        try:
            # 'replace' evita crash por caracteres extraños en el log
            line_str = line.decode('utf-8', errors='replace').strip()
        except:
            continue

        # --- PALABRAS CLAVE MAESTRAS (XIAOMI / ANDROID PURO) ---
        
        # 1. "CallState: 2" -> Código universal de Android para OFFHOOK (Contestada)
        # 2. "GET_CURRENT_CALLS" con estado ACTIVE -> Muy común en Xiaomi
        # 3. "setTo active" -> Transición directa
        
        if "CallState: 2" in line_str or "GET_CURRENT_CALLS" in line_str and "ACTIVE" in line_str:
            print(f"   🟢 ¡CONEXIÓN DETECTADA!: {line_str[-50:]}") # Muestra qué detectó
            conectado = True
            break
        
        # Detección de Colgado (IDLE / DISCONNECTED)
        # Ignoramos los primeros 4 segundos para evitar falsos positivos al iniciar la llamada
        if (time.time() - start_time) > 4:
            if "CallState: 0" in line_str or "DISCONNECTED" in line_str:
                print("   ❌ Llamada finalizada (IDLE detectado).")
                break

    # Importante: Matar el proceso logcat para no dejar zombies en Linux
    process.terminate()
    return conectado

def realizar_llamada(numero):
    print(f"----------------------------------------")
    print(f"📞 Procesando: {numero}")
    
    # 1. Despertar
    adb_cmd("input keyevent 26")
    adb_cmd("input keyevent 82")
    time.sleep(1)

    # 2. Marcar
    print("   -> Marcando...")
    adb_cmd(f"am start -a android.intent.action.CALL -d tel:{numero}")
    
    # 3. ESPERAR A QUE CONTESTEN (Logcat)
    se_conecto = esperar_contestacion_logcat_radio()

    if se_conecto:
        # Pausa vital: Esperar que el audio cambie de "tono de llamada" a "voz"
        time.sleep(1.5)

        # 4. Activar Altavoz
        print(f"   -> 🔊 Activando Altavoz...")
        adb_cmd(f"input tap {BTN_ALTAVOZ_X} {BTN_ALTAVOZ_Y}")
        time.sleep(0.5)

        # 5. REPRODUCIR AUDIO (Doble check)
        print("   -> ▶️ Reproduciendo mensaje...")
        
        # A) Asegurar volumen al máximo OTRA VEZ
        adb_cmd("input keyevent 24")
        adb_cmd("input keyevent 24")
        
        # B) Lanzar reproductor
        adb_cmd(f"am start -a android.intent.action.VIEW -d file://{ARCHIVO_AUDIO_CEL} -t audio/mp3")
        
        # C) Presionar "Play" virtualmente por si arranca en pausa
        time.sleep(1)
        adb_cmd("input keyevent 126") # KEYCODE_MEDIA_PLAY

        # 6. Esperar duración
        print(f"   -> Esperando {DURACION_AUDIO} segundos...")
        time.sleep(DURACION_AUDIO)
        print("   -> ✅ Mensaje entregado.")
    else:
        print("   -> ⚠️ No contestaron.")

    # 7. Colgar
    print("   -> 📴 Colgando...")
    adb_cmd("input keyevent ENDCALL")         
    time.sleep(3) 

# --- BLOQUE PRINCIPAL ---
if __name__ == "__main__":
    if not os.path.exists(ARCHIVO_AUDIO_LOCAL):
        print(f"❌ Falta {ARCHIVO_AUDIO_LOCAL}")
        sys.exit()
    
    if not os.path.exists(ARCHIVO_CSV):
        print(f"❌ Falta {ARCHIVO_CSV}")
        sys.exit()

    preparar_sistema()

    numeros = []
    try:
        with open(ARCHIVO_CSV, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip().isdigit():
                    numeros.append(row[0].strip())
    except Exception as e:
        print(f"❌ Error leyendo CSV: {e}")
        sys.exit()

    print(f"✅ Lista cargada: {len(numeros)} números.")
    print("🚀 Iniciando campaña (Modo Logcat Radio)...")

    for tel in numeros:
        realizar_llamada(tel)
        print("⏳ Enfriamiento (5s)...")
        time.sleep(5)
