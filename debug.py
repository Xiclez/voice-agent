import subprocess
import time

device_id = "192.168.1.83:39393"

print(f"--- RASTREADOR DE LOGS (LOGCAT) PARA {device_id} ---")
print("1. Limpiando logs antiguos...")
try:
    subprocess.run(f"adb -s {device_id} logcat -c", shell=True)
except:
    pass

print("2. ESCUCHANDO... (Haz la llamada manual ahora y CONTESTA)")
print("Busca líneas que aparezcan JUSTO cuando contestas.")
print("-------------------------------------------------------")

# Iniciamos el proceso de lectura de logs en tiempo real
# Filtramos por palabras clave de audio
cmd = f"adb -s {device_id} logcat -v time"
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

palabras_clave = ["setMode", "AUDIO_MODE", "mode=", "AudioState", "setPhoneState", "CallState"]

try:
    while True:
        line = process.stdout.readline()
        if not line:
            break
            
        line_str = line.decode('utf-8', errors='ignore').strip()
        
        # Filtramos para ver solo lo interesante
        # Si alguna palabra clave está en la línea, la imprimimos
        if any(keyword in line_str for keyword in palabras_clave):
            # Imprimimos solo si no es basura repetitiva
            if "DisplayPowerController" not in line_str and "cast" not in line_str:
                print(line_str)

except KeyboardInterrupt:
    print("\nDetenido.")