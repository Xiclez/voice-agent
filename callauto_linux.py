import os
import time
import csv
import subprocess
import sys

# --- CONFIGURACIÓN ---
# ID del dispositivo (Cable USB) - NO CAMBIAR SI ES EL MISMO CEL
ADB_ID = "426fbf59" 

# Archivos
ARCHIVO_AUDIO_LOCAL = "mensaje.mp3"
ARCHIVO_AUDIO_CEL   = "/sdcard/mensaje.mp3"
ARCHIVO_CSV         = "numeros.csv"

# COORDENADAS BOTÓN ALTAVOZ (Verifica con scrcpy)
BTN_ALTAVOZ_X = 850 
BTN_ALTAVOZ_Y = 1620 

# Duración del audio
DURACION_AUDIO = 20

def adb_cmd(comando):
    """Ejecuta comando shell directo (sin retorno)"""
    full_cmd = f"adb -s {ADB_ID} shell {comando}"
    os.system(full_cmd)

def preparar_sistema():
    """Sube el audio y arregla permisos"""
    print("📂 Preparando archivos en el celular...")
    # 1. Subir archivo
    os.system(f"adb -s {ADB_ID} push {ARCHIVO_AUDIO_LOCAL} {ARCHIVO_AUDIO_CEL}")
    # 2. DAR PERMISOS (Crucial para que suene)
    # A veces el reproductor no puede leer archivos pushed por root/adb
    adb_cmd(f"chmod 777 {ARCHIVO_AUDIO_CEL}")

def subir_volumen_media():
    """Sube el volumen multimedia al máximo"""
    print("   🔊 Forzando volumen multimedia...")
    for _ in range(15):
        adb_cmd("input keyevent 24") # VOLUME_UP

def esperar_evento_logcat_linux(timeout=60):
    """
    Versión portada y corregida de tu script de Windows.
    Lee el flujo de Logcat en tiempo real.
    """
    print(f"   ⏳ Esperando contestación (Máx {timeout}s)...")
    
    # 1. Limpiar buffer antiguo
    os.system(f"adb -s {ADB_ID} logcat -c")

    # 2. Iniciar lectura (Sin shell=True para mejor control en Linux)
    cmd = ["adb", "-s", ADB_ID, "logcat", "-v", "time"]
    
    # Usamos subprocess.PIPE para leer línea por línea
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    start_time = time.time()
    conectado = False

    while (time.time() - start_time) < timeout:
        # Leer línea (bloqueante pero rápido)
        line = process.stdout.readline()
        if not line: continue
        
        try:
            line_str = line.decode('utf-8', errors='ignore').strip()
        except:
            continue

        # --- LÓGICA DE DETECCIÓN ---
        # "CallState: 2" = OFFHOOK (Contestaron)
        # "CallState: 0" = IDLE (Colgaron)
        # "EXTRA_STATE_OFFHOOK" = Otra variante común
        
        if "CallState: 2" in line_str or "EXTRA_STATE_OFFHOOK" in line_str:
            print(f"   🟢 CONEXIÓN DETECTADA: {line_str[-20:]}")
            conectado = True
            break
        
        # Si detectamos que colgaron (IDLE) pero IGNORAMOS los primeros 3 segundos
        # (porque al marcar a veces pasa brevemente por idle)
        if ("CallState: 0" in line_str or "EXTRA_STATE_IDLE" in line_str) and (time.time() - start_time) > 4:
            print("   ❌ Llamada terminada (IDLE detectado).")
            break

    # Matar el proceso de logcat para no dejar basura
    process.terminate()
    return conectado

def realizar_llamada(numero):
    print(f"----------------------------------------")
    print(f"📞 Procesando: {numero}")
    
    # 1. Despertar
    adb_cmd("input keyevent 26") # Power
    adb_cmd("input keyevent 82") # Unlock
    time.sleep(1)

    # 2. Marcar
    print("   -> Marcando...")
    adb_cmd(f"am start -a android.intent.action.CALL -d tel:{numero}")
    
    # 3. Esperar a que contesten (Lógica Logcat Restaurada)
    se_conecto = esperar_evento_logcat_linux()

    if se_conecto:
        # Pausa crítica para que el audio del sistema cambie de "Tono" a "Voz"
        time.sleep(1.5)

        # 4. Activar Altavoz
        print(f"   -> 🔊 Activando Altavoz...")
        adb_cmd(f"input tap {BTN_ALTAVOZ_X} {BTN_ALTAVOZ_Y}")
        time.sleep(0.5)

        # 5. REPRODUCIR AUDIO (Estrategia Reforzada)
        print("   -> ▶️ Reproduciendo mensaje...")
        
        # A) Subir volumen primero
        subir_volumen_media()
        
        # B) Lanzar Intent de Audio (Nativo)
        # El flag -t audio/mp3 ayuda a que Android sepa qué app abrir
        adb_cmd(f"am start -a android.intent.action.VIEW -d file://{ARCHIVO_AUDIO_CEL} -t audio/mp3")

        # C) Alternativa de "Play" por si se pausa al abrir (simular tecla PLAY)
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
        print(f"❌ Error: No existe {ARCHIVO_AUDIO_LOCAL}")
        sys.exit()
    
    if not os.path.exists(ARCHIVO_CSV):
        print(f"❌ Error: No existe {ARCHIVO_CSV}")
        sys.exit()

    preparar_sistema()

    numeros_a_llamar = []
    try:
        with open(ARCHIVO_CSV, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    telf = row[0].strip()
                    if telf.isdigit(): numeros_a_llamar.append(telf)
    except Exception as e:
        print(f"❌ Error CSV: {e}")
        sys.exit()

    print(f"✅ Lista cargada: {len(numeros_a_llamar)} números.")
    print("🚀 Iniciando campaña...")

    for telefono in numeros_a_llamar:
        realizar_llamada(telefono)
        print("⏳ Enfriamiento (5s)...")
        time.sleep(5)

    print("\n🏁 Fin.")
