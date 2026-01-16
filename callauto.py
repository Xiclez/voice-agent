import os
import time
import subprocess
import pygame
import csv
import json
import random
from datetime import datetime

# Intentamos importar la librería nueva de audio
try:
    from pygame._sdl2.audio import get_audio_device_names
    use_new_sdl = True
except ImportError:
    use_new_sdl = False

# --- CONFIGURACIÓN GENERAL ---
device_id = "192.168.1.83:39393"
archivo_csv = "lista_numeros.csv"
archivo_log = "historial.json"
numero_a_transferir = "6144101661" # Número al que desviarás las llamadas entrantes

# --- AUDIOS ---
# A/B Testing para Salientes
audio_opcion_A = "mensajeULAL1.mp3"
audio_opcion_B = "mensajeULAL2.mp3"
# Audio para Entrantes
audio_recepcion = "mensajeFrontDeskULAL.mp3"

# --- COORDENADAS (AJUSTAR SEGÚN TU PANTALLA) ---
# Transferencia de Audio al PC (Ya las tienes)
btn_audio_source_x = 650
btn_audio_source_y = 1844
btn_pc_select_x = 500
btn_pc_select_y = 1300

# Transferencia de Llamada (NUEVAS - Para desviar entrantes)
# Tienes que buscar estas coordenadas en tu pantalla de llamada activa
btn_add_call_x = 800  # Botón "+" o "Añadir llamada"
btn_add_call_y = 1500
btn_merge_call_x = 800 # Botón "Unir" o "Fusionar" (aparece tras marcar al segundo)
btn_merge_call_y = 1500
# ------------------------------------------------

# --- GESTIÓN DE DATOS (CSV / JSON) ---
def cargar_historial():
    if not os.path.exists(archivo_log):
        return {}
    with open(archivo_log, 'r') as f:
        return json.load(f)

def guardar_historial(historial):
    with open(archivo_log, 'w') as f:
        json.dump(historial, f, indent=4)

def obtener_siguiente_numero(historial):
    if not os.path.exists(archivo_csv):
        print("❌ No se encontró lista_numeros.csv")
        return None

    with open(archivo_csv, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row: continue
            numero = row[0].strip() # Asumimos número en primera columna
            
            # Si el número NO está en el historial, es el elegido
            if numero not in historial:
                return numero
    return None

# --- AUDIO SYSTEM ---
def iniciar_motor_audio():
    print("--- INICIANDO MOTOR DE AUDIO ---")
    pygame.init()
    pygame.mixer.init()
    
    vm_device = None
    if use_new_sdl:
        try:
            devices = get_audio_device_names(False)
            for name in devices:
                if "VoiceMeeter Input" in name:
                    vm_device = name
                    break
        except: pass

    if vm_device:
        print(f"-> Conectado a: {vm_device}")
        pygame.mixer.quit()
        pygame.mixer.init(devicename=vm_device)
    else:
        print("-> Usando dispositivo predeterminado.")
        pygame.mixer.init()

def reproducir_audio(archivo):
    print(f"   📢 Reproduciendo: {archivo}")
    try:
        pygame.mixer.music.load(archivo)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.5)
            print(".", end="", flush=True)
        print("\n   ✅ Audio finalizado.")
    except Exception as e:
        print(f"\n❌ Error reproduciendo audio: {e}")

# --- ADB TOOLS ---
def transferir_audio_a_pc():
    print("   -> 🔀 Transfiriendo audio a PC (Bluetooth)...")
    time.sleep(1.0)
    os.system(f"adb -s {device_id} shell input tap {btn_audio_source_x} {btn_audio_source_y}")
    time.sleep(1.0)
    os.system(f"adb -s {device_id} shell input tap {btn_pc_select_x} {btn_pc_select_y}")
    time.sleep(1.5)

def realizar_transferencia_llamada(numero_destino):
    """
    Simula: Añadir llamada -> Marcar -> Unir (Conferencia/Transferencia)
    """
    print(f"   -> 📞 Transfiriendo llamada a {numero_destino}...")
    
    # 1. Clic en Añadir Llamada
    os.system(f"adb -s {device_id} shell input tap {btn_add_call_x} {btn_add_call_y}")
    time.sleep(1.5)
    
    # 2. Escribir el número (ADB permite escribir texto directo)
    os.system(f"adb -s {device_id} shell input text {numero_destino}")
    time.sleep(1)
    
    # 3. Llamar (Keyevent 5)
    os.system(f"adb -s {device_id} shell am start -a android.intent.action.CALL -d tel:{numero_destino}")
    time.sleep(5) # Esperar a que conecte la segunda línea
    
    # 4. Fusionar / Unir
    print("   -> Fusionando líneas...")
    os.system(f"adb -s {device_id} shell input tap {btn_merge_call_x} {btn_merge_call_y}")

# --- Detección Logcat ---
def esperar_evento_logcat(trigger_text, timeout=60, incoming=False):
    print(f"[{time.strftime('%H:%M:%S')}] Esperando: '{trigger_text}'...")
    try: os.system(f"adb -s {device_id} logcat -c")
    except: pass
    
    cmd = f"adb -s {device_id} logcat -v time"
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    start_time = time.time()
    
    while (time.time() - start_time) < timeout:
        line = process.stdout.readline()
        if not line: continue
        line_str = line.decode('utf-8', errors='ignore').strip()
        
        # Si buscamos llamada entrante (RINGING)
        if incoming and ("RINGING" in line_str or "CallState: 1" in line_str):
             print(f"   🔔 ¡LLAMADA ENTRANTE DETECTADA!")
             process.terminate()
             return "RINGING"

        if trigger_text in line_str:
            print(f"   -> ¡DETECTADO!: {trigger_text}")
            process.terminate()
            return True
            
        if "DISCONNECTED" in line_str and not incoming:
            process.terminate()
            return False
            
    try: process.terminate()
    except: pass
    return False

# --- MODOS PRINCIPALES ---

def modo_campana_saliente():
    historial = cargar_historial()
    
    while True:
        target = obtener_siguiente_numero(historial)
        if not target:
            print("\n🏁 No hay más números pendientes en el CSV.")
            break
            
        # Coin Flip (A/B Testing)
        audio_elegido = random.choice([audio_opcion_A, audio_opcion_B])
        
        print(f"\n----------------------------------------")
        print(f"📞 Llamando a: {target} | Audio: {audio_elegido}")
        
        os.system(f"adb -s {device_id} shell am start -a android.intent.action.CALL -d tel:{target}")
        
        if esperar_evento_logcat("DIALING -> ACTIVE"):
            print("   🟢 CONECTADO")
            transferir_audio_a_pc()
            reproducir_audio(audio_elegido)
            
            # Registrar éxito
            historial[target] = {
                "fecha": str(datetime.now()),
                "status": "completado",
                "audio_usado": audio_elegido
            }
            guardar_historial(historial)
            
            print("   -> Colgando...")
            os.system(f"adb -s {device_id} shell input keyevent 6")
        else:
            print("   ❌ No contestaron / Ocupado.")
            # Registrar fallo (opcional, para no reintentar infinitamente)
            historial[target] = {
                "fecha": str(datetime.now()),
                "status": "fallido",
                "audio_usado": "ninguno"
            }
            guardar_historial(historial)
            os.system(f"adb -s {device_id} shell input keyevent 6")
            
        print("   -> Esperando 5s antes de la siguiente llamada...")
        time.sleep(5)

def modo_recepcion_entrante():
    print(f"\n🛡️ MODO RECEPCIÓN ACTIVO")
    print(f"   Esperando llamadas para transferir a: {numero_a_transferir}")
    
    while True:
        # Esperamos indefinidamente por "RINGING"
        # Usamos un timeout alto o loop infinito
        evento = esperar_evento_logcat("RINGING", timeout=3600, incoming=True)
        
        if evento == "RINGING":
            print("   📞 ¡LLAMADA ENTRANTE! Contestando...")
            # Keyevent 5 es el botón físico de "Llamar/Contestar"
            os.system(f"adb -s {device_id} shell input keyevent 5")
            
            # Esperamos a que la llamada pase a ACTIVE
            if esperar_evento_logcat("ACTIVE", timeout=10):
                transferir_audio_a_pc()
                
                print("   🗣️ Reproduciendo bienvenida Front Desk...")
                reproducir_audio(audio_recepcion)
                
                print("   🔀 Iniciando conmutación/transferencia...")
                realizar_transferencia_llamada(numero_a_transferir)
                
                # Una vez fusionado, podemos salir o esperar que cuelguen
                print("   ✅ Llamada transferida. Esperando que finalice.")
                esperar_evento_logcat("DISCONNECTED", timeout=300)
                print("   -> Llamada finalizada. Volviendo a esperar...")
                
            else:
                print("   ❌ Error al intentar contestar.")

# --- MENÚ ---
if __name__ == "__main__":
    iniciar_motor_audio()
    print("\nSelecciona modo:")
    print("1. Campaña Saliente (CSV + A/B Test + JSON)")
    print("2. Recepción Entrante (Front Desk + Transferencia)")
    opcion = input("Opción: ")
    
    if opcion == "1":
        modo_campana_saliente()
    elif opcion == "2":
        modo_recepcion_entrante()
    else:
        print("Opción no válida")