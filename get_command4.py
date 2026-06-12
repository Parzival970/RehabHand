import pyaudio
import wave
import numpy as np
import serial
import time
from faster_whisper import WhisperModel

# --- CONFIGURAZIONE ---
SER_PORT = '/dev/ttyACM0' 
BAUD = 115200
MIC_ID = 24  
SOGLIA_VOL = 500
RATE = 48000

try:
    arduino = serial.Serial(SER_PORT, BAUD, timeout=0.1)
    time.sleep(2)
    print(f"Connesso ad Arduino su {SER_PORT}")
except:
    print("ERRORE: Controlla permessi seriali (chmod 666 /dev/ttyACM0)")
    exit()

model = WhisperModel("base", device="cuda", compute_type="int8_float16")

def invia_e_attendi(stringa):
    arduino.write((stringa + "\n").encode())
    print(f"   [JETSON] Inviato: {stringa}")
    time.sleep(0.1)
    while arduino.in_waiting:
        risposta = arduino.readline().decode('utf-8').strip()
        if ">>> ACK:" in risposta:
            print(f"   [ARDUINO] {risposta}")

def ascolta():
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, input_device_index=MIC_ID)
    print("\n--- ASCOLTO (3s) ---")
    frames = []
    max_vol = 0
    for _ in range(0, int(RATE / 1024 * 3)):
        data = stream.read(1024, exception_on_overflow=False)
        vol = np.abs(np.frombuffer(data, dtype=np.int16)).mean()
        if vol > max_vol: max_vol = vol
        frames.append(data)
    stream.stop_stream(); stream.close(); p.terminate()
    if max_vol < SOGLIA_VOL: return ""
    
    wf = wave.open("tmp.wav", 'wb')
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE)
    wf.writeframes(b''.join(frames)); wf.close()
    
    segments, _ = model.transcribe("tmp.wav", language="it")
    return " ".join([s.text for s in segments]).lower()

def interpreta(testo):
    if any(x in testo for x in ["stop", "smetti", "basta", "dolore"]):
        invia_e_attendi("stop")
        return
    dita = {"mignolo":"1", "anulare":"2", "medio":"3", "indice":"4", "pollice":"5"}
    act = "on" if "chiudi" in testo else "off" if "apri" in testo else None
    if not act: return
    if any(x in testo for x in ["mano", "tutto", "pugno"]):
        invia_e_attendi("allon" if act == "on" else "alloff")
    else:
        for nome, num in dita.items():
            if nome in testo: invia_e_attendi(f"{num}{act}")

try:
    while True:
        if arduino.in_waiting:
            line = arduino.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith("P:"): print(f"\r{line}      ", end="")
        cmd = ascolta()
        if cmd:
            print(f"\nVoce: '{cmd}'")
            interpreta(cmd)
except KeyboardInterrupt:
    arduino.close()