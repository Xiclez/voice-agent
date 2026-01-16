import subprocess
import time
import os
import signal

# --- CONFIGURACIÓN ---
ADB_ID = "426fbf59"       # Tu ID USB
NUMERO_PRUEBA = "3330547185" # <--- ¡CAMBIA ESTO!
ARCHIVO_SALIDA = "log_captura.txt"

def capturar_log_forense():
    print(f"🧹 Limpiando buffers antiguos de {ADB_ID}...")
    os.system(f"adb -s {ADB_ID} logcat -c")

    print(f"🔴 INICIANDO GRABACIÓN DE LOGCAT en {ARCHIVO_SALIDA}...")
    
    # Abrimos el archivo para escribir
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        # Iniciamos logcat en segundo plano escribiendo al archivo
        # Usamos -v time para ver los segundos exactos
        process = subprocess.Popen(
            ["adb", "-s", ADB_ID, "logcat", "-v", "time"], 
            stdout=f,
            stderr=subprocess.PIPE
        )

        try:
            print("------------------------------------------------")
            print(f"📞 MARCANDO A: {NUMERO_PRUEBA}")
            print("⚠️  POR FAVOR: CONTESTA LA LLAMADA MANUALMENTE")
            print("------------------------------------------------")
            
            # Realizar la llamada
            os.system(f"adb -s {ADB_ID} shell am start -a android.intent.action.CALL -d tel:{NUMERO_PRUEBA}")

            # Damos tiempo para que contestes y hables (15 segundos)
            for i in range(15, 0, -1):
                print(f"⏳ Grabando... Quedan {i} segundos (¡HABLA AHORA!)")
                time.sleep(1)

            print("------------------------------------------------")
            print("📴 TIEMPO TERMINADO. COLGANDO...")
            os.system(f"adb -s {ADB_ID} shell input keyevent ENDCALL")
            
        finally:
            # Matamos el proceso de logcat limpiamente
            print("💾 Guardando archivo...")
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

    print(f"\n✅ HECHO. El archivo '{ARCHIVO_SALIDA}' tiene los datos.")
    print("🔎 Ahora vamos a buscar el tesoro...")

if __name__ == "__main__":
    capturar_log_forense()
