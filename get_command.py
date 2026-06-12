import pyaudio
import wave
import numpy as np
from faster_whisper import WhisperModel
import logging
import os

# --- CONFIGURAZIONE ---
DEVICE = "cpu" # si usa "cpuu" o "cuda" su PC, ma su Jetson è meglio "cpu" con modello "small" per prestazioni ottimali
MODEL_SIZE = "small" #  "base" è più preciso ma più lento, "small" è un buon compromesso per Jetson, anche "tiny" è un'opzione se vuoi più velocità a scapito di precisione
MIC_ID = 0          # controlla id da check_audio.py e aggiorna se necessario
SOGLIA_VOLUME = 600  
RATE_NATIVO = 48000  # Frequenza standard per USB su Jetson

# Pulizia log
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

print("Inizializzazione Whisper su GPU Jetson...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8") # int8 è più veloce su CPU, ma se usi "cuda" su PC puoi provare "float16" per migliore precisione

def ascolta_comando():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RECORD_SECONDS = 3

    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE_NATIVO, 
                        input=True, input_device_index=MIC_ID, 
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Errore: non riesco ad aprire l'ID {MIC_ID}. Dettaglio: {e}")
        p.terminate()
        return ""

    print(f"\n--- IN ASCOLTO (Parla ora...) ---")
    frames = []
    max_vol = 0

    for _ in range(0, int(RATE_NATIVO / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        attuale = np.abs(audio_data).mean()
        if attuale > max_vol: max_vol = attuale
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    if max_vol < SOGLIA_VOLUME:
        print(f"   [Volume troppo basso: {int(max_vol)}]")
        return ""

    # Salvataggio audio temporaneo
    nome_file = "comando_jetson.wav"
    wf = wave.open(nome_file, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE_NATIVO)
    wf.writeframes(b''.join(frames))
    wf.close()

    # Trascrizione AI
    segments, _ = model.transcribe(nome_file, language="it")
    testo = " ".join([s.text for s in segments]).lower()
    return testo

def muovi_guanto(testo):
    dita = ["pollice", "indice", "medio", "anulare", "mignolo"]
    print(f"Comando ricevuto: '{testo.strip()}'")
    
    if "chiudi" in testo:
        azione = "CHIUSURA"
    elif "apri" in testo:
        azione = "APERTURA"
    else: 
        print("   -> Azione non riconosciuta (usa 'apri' o 'chiudi')")
        return

    # Placeholder per le valvole
    if any(p in testo for p in ["mano", "pugno", "tutto"]):
        print(f"   [SIMULAZIONE] Elettrovalvola: {azione} TOTALE")
    else:
        for d in dita:
            if d in testo:
                print(f"   [SIMULAZIONE] Elettrovalvola: {azione} dito {d.upper()}")

# --- AVVIO ---
try:
    print("\nSistema pronto sulla Jetson Orin Nano.")
    print("Indossa gli auricolari e prova a dire 'Chiudi mano' o 'Apri indice'.")
    while True:
        cmd = ascolta_comando()
        if cmd: 
            muovi_guanto(cmd)
except KeyboardInterrupt:
    print("\nSpegnimento in corso...")