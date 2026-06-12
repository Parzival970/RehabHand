import pyaudio
import wave
import numpy as np
import serial
import time
from faster_whisper import WhisperModel

#prima di lanciare il codice, scrivi "sudo chmod 666 /dev/ttyACM0" (cambiare in /dev/ttyUSB0 se necessario) per dare i permessi alla porta seriale, 
# altrimenti il codice non riuscirà a comunicare con Arduino

# --- CONFIGURAZIONE ---
SER_PORT = '/dev/ttyACM0' # Cambia in /dev/ttyUSB0 se necessario
BAUD_RATE = 115200
MIC_ID = 24  #Id dell'auricolare USB, controlla con check_audio.py e aggiorna se necessario
SOGLIA_VOLUME = 300 # Soglia di volume per considerare un comando valido, regola se necessario
RATE_NATIVO = 48000 

# Inizializzazione Seriale
try:
    arduino = serial.Serial(SER_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(2)
    print(f"Connesso ad Arduino su {SER_PORT}")
except:
    print("Errore: Arduino non trovato.")
    exit()

# Modello Tiny su CPU per stabilità sulla Orin Nano
model = WhisperModel("tiny", device="cpu", compute_type="int8") # int8 è più veloce su CPU, ma se usi "cuda" su PC puoi provare "float16" per migliore precisione

def invia(stringa):
    arduino.write((stringa + "\n").encode())
    print(f"   [SERIAL SEND] -> {stringa}")

def ascolta_comando():
    CHUNK, FORMAT, CHANNELS = 1024, pyaudio.paInt16, 1
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE_NATIVO, input=True, input_device_index=MIC_ID)
    
    print("\n--- IN ASCOLTO ---")
    frames, max_vol = [], 0
    for _ in range(0, int(RATE_NATIVO / CHUNK * 3)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        vol = np.frombuffer(data, dtype=np.int16).mean()
        if abs(vol) > max_vol: max_vol = abs(vol)
        frames.append(data)
    
    stream.stop_stream(); stream.close(); p.terminate()
    
    if max_vol < SOGLIA_VOLUME: return ""
    
    wf = wave.open("temp.wav", 'wb')
    wf.setnchannels(CHANNELS); wf.setsampwidth(p.get_sample_size(FORMAT)); wf.setframerate(RATE_NATIVO)
    wf.writeframes(b''.join(frames)); wf.close()
    
    segments, _ = model.transcribe("temp.wav", language="it")
    return " ".join([s.text for s in segments]).lower()

def interpreta(testo):
    dita = {"mignolo":"1", "anulare":"2", "medio":"3", "indice":"4", "pollice":"5"}
    if "chiudi" in testo: act = "on"
    elif "apri" in testo: act = "off"
    else: return

    if any(x in testo for x in ["mano", "pugno", "tutto"]):
        invia("allon" if act == "on" else "alloff")
    else:
        for nome, num in dita.items():
            if nome in testo: invia(f"{num}{act}")

try:
    while True:
        vocal_cmd = ascolta_comando()
        if vocal_cmd:
            print(f"Riconosciuto: {vocal_cmd}")
            interpreta(vocal_cmd)
        # Leggi pressione da Arduino se disponibile
        if arduino.in_waiting:
            print(f"Dati Arduino: {arduino.readline().decode().strip()}")
except KeyboardInterrupt:
    arduino.close()