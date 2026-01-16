import os
import time
import csv
import subprocess
import sys
import signal

# --- CONFIGURACIÓN ---
ADB_ID = "426fbf59" 

# Archivos
ARCHIVO_AUDIO_LOCAL = "mensaje.mp3"
ARCHIVO_AUDIO_CEL   = "/sdcard/mensaje.mp3"
ARCHIVO_CSV         = "numeros.csv"

# COORDENADAS ALTAVOZ (De tu scrcpy)
BTN_ALTAVOZ_X = 850 
BTN_ALTAVOZ_Y = 1620 

# Duración del audio
DURACION_AUDIO = 20

def adb_cmd(comando):
    os.system(f"adb -s {ADB_ID} shell {comando}")

def preparar_sistema():
    print("📂 Preparando sistema...")
    os.system(f"adb -s {ADB_ID} push {ARCHIVO_AUDIO_LOCAL} {ARCHIVO_AUDIO_CEL}")
    adb_cmd(f"chmod 777 {ARCHIVO_AUDIO_CEL}")
    # Subir volumen preventivo
    for _ in range(5): adb_cmd("input keyevent 24")

def esperar_contestacion_analisis_log(timeout=60):
    """
    Busca la transición específica '-> ACTIVE' en el log de Telecom.
    Basado en tu log_captura.txt línea 3795.
    """
    print(f"   ⏳ Escaneando log por '-> ACTIVE' (Máx {timeout}s)...")
    
    # Limpiamos buffer
    os.system(f"adb -s {ADB_ID} logcat -c")

    # Filtramos por 'Telecom' para reducir ruido y CPU
    cmd = ["adb", "-s", ADB_ID, "logcat", "-v", "time", "-s", "Telecom:I"]
    
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start_time = time.time()
    
    conectado = False

    while (time.time() - start_time) < timeout:
        line = process.stdout.readline()
        if not line: continue
        
        try:
            line_str = line.decode('utf-8', errors='ignore').strip()
        except:
            continue

        # --- DETECCIÓN QUIRÚRGICA BASADA EN TU LOG ---
        # Log real: CallsManager: setCallState DIALING -> ACTIVE
        if "-> ACTIVE" in line_str:
            print(f"   🟢 ¡CONEXIÓN CONFIRMADA!: {line_str}")
            conectado = True
            break
            
        # Detección de desconexión
        # Log real: Event: RecordEntry ... REQUEST_DISCONNECT
        if "REQUEST_DISCONNECT" in line_str or "setCallState ACTIVE -> DISCONNECTED" in line_str:
             # Ignoramos si esto pasa en los primeros 2 segundos (transiciones raras)
            if (time.time() - start_time) > 2:
                print(f"   ❌ Llamada finalizada: {line_str}")
                break

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
    
    # 3. ESPERAR A QUE CONTESTEN (Lógica V5)
    se_conecto = esperar_contestacion_analisis_log()

    if se_conecto:
        time.sleep(1.5) # Pausa de audio

        # 4. Activar Altavoz
        print(f"   -> 🔊 Activando Altavoz...")
        adb_cmd(f"input tap {BTN_ALTAVOZ_X} {BTN_ALTAVOZ_Y}")
        time.sleep(0.5)

        # 5. REPRODUCIR AUDIO
        print("   -> ▶️ Reproduciendo mensaje...")
        
        # Refuerzo volumen
        adb_cmd("input keyevent 24")
        adb_cmd("input keyevent 24")
        
        # Play (VLC/Nativo)
        adb_cmd(f"am start -a android.intent.action.VIEW -d file://{ARCHIVO_AUDIO_CEL} -t audio/mp3")
        time.sleep(1)
        adb_cmd("input keyevent 126") # KEYCODE_MEDIA_PLAY

        # 6. Esperar duración
        print(f"   -> Esperando {DURACION_AUDIO} segundos...")
        time.sleep(DURACION_AUDIO)
        print("   -> ✅ Mensaje entregado.")
    else:
        print("   -> ⚠️ No contestaron o buzón.")

    # 7. Colgar
    print("   -> 📴 Colgando...")
    adb_cmd("input keyevent ENDCALL")         
    time.sleep(3) 

# --- MAIN ---
if __name__ == "__main__":
    if not os.path.exists(ARCHIVO_AUDIO_LOCAL):
        print("❌ Falta audio")
        sys.exit()

    preparar_sistema()

    numeros = []
    try:
        with open(ARCHIVO_CSV, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row and row[0].strip().isdigit():
                    numeros.append(row[0].strip())
    except: pass

    print(f"✅ Lista cargada: {len(numeros)} números.")
    
    for tel in numeros:
        realizar_llamada(tel)
        print("⏳ Enfriamiento (5s)...")
        time.sleep(5)
