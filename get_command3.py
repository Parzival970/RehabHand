import pyaudio
import wave
import numpy as np
import serial
import time
from faster_whisper import WhisperModel

#prima di lanciare il codice, scrivi "sudo chmod 666 /dev/ttyACM0" (cambiare in /dev/ttyUSB0 se necessario) per dare i permessi alla porta seriale, 
# altrimenti il codice non riuscirà a comunicare con Arduino

# --- CONFIGURAZIONE ---
SER_PORT = '/dev/ttyACM0' 
BAUD = 115200
MIC_ID = 24  
SOGLIA_VOL = 500
RATE = 48000

try:
    arduino = serial.Serial(SER_PORT, BAUD, timeout=0.1)
    time.sleep(2)
    print("Connesso ad Arduino!")
except:
    print("Errore: Porta ACM0 non trovata. Prova 'sudo chmod 666 /dev/ttyACM0'")
    exit()

model = WhisperModel("tiny", device="cpu", compute_type="int8")

def invia(stringa):
    arduino.write((stringa + "\n").encode())
    print(f"   [SERIAL SEND] -> {stringa}")

def ascolta_comando():
    CHUNK, FORMAT, CHANNELS = 1024, pyaudio.paInt16, 1
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=MIC_ID)
    
    print("\n--- IN ASCOLTO ---")
    frames, max_vol = [], 0
    for _ in range(0, int(RATE / CHUNK * 3)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        vol = np.abs(np.frombuffer(data, dtype=np.int16)).mean()
        if vol > max_vol: max_vol = vol
        frames.append(data)
    
    stream.stop_stream(); stream.close(); p.terminate()
    if max_vol < SOGLIA_VOL: return ""
    
    wf = wave.open("temp.wav", 'wb')
    wf.setnchannels(CHANNELS); wf.setsampwidth(p.get_sample_size(FORMAT)); wf.setframerate(RATE)
    wf.writeframes(b''.join(frames)); wf.close()
    
    segments, _ = model.transcribe("temp.wav", language="it")
    return " ".join([s.text for s in segments]).lower()

def interpreta(testo):
    # Emergenza
    if any(x in testo for x in ["stop", "smetti", "basta", "dolore"]):
        invia("stop")
        return

    dita = {"mignolo":"1", "anulare":"2", "medio":"3", "indice":"4", "pollice":"5"}
    
    # Determina Azione
    if "chiudi" in testo or "on" in testo: act = "on"
    elif "apri" in testo or "off" in testo: act = "off"
    else: return

    # Costruisce stringa per la tua handleSerial()
    if any(x in testo for x in ["mano", "tutto", "pugno"]):
        invia("allon" if act == "on" else "alloff")
    else:
        for nome, num in dita.items():
            if nome in testo:
                invia(f"{num}{act}") # Es: "1on", "4off"

try:
    while True:
        vocal_cmd = ascolta_comando()
        if vocal_cmd:
            print(f"Voce: {vocal_cmd}")
            interpreta(vocal_cmd)
        
        # Stampa i log di Arduino (Pressione e Stato Valvole)
        if arduino.in_waiting:
            print(f"Arduino: {arduino.readline().decode().strip()}")
except KeyboardInterrupt:
    arduino.close()