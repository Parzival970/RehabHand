import time
import serial
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

SER_PORT = "/dev/ttyACM0"
BAUD = 115200
MIC_ID = 0

CHANNELS = 2
INPUT_RATE = 48000
WHISPER_RATE = 16000
CHUNK = 1024

SOGLIA_VOL = 220
START_FRAMES = 2
SILENCE_FRAMES = 14
PRE_ROLL_FRAMES = 12
MAX_RECORD_SECONDS = 5.0
MIN_RECORD_SECONDS = 0.8

ACK_TIMEOUT_S = 0.6


def connetti_seriale():
    try:
        ard = serial.Serial(SER_PORT, BAUD, timeout=0.05)
        time.sleep(2)
        print(f"Connesso ad Arduino su {SER_PORT}")
        return ard
    except Exception as e:
        print("ERRORE: Controlla permessi seriali (chmod 666 /dev/ttyACM0)")
        print("Dettaglio:", e)
        raise SystemExit(1)

arduino = connetti_seriale()

# Sostituisci la tua riga del modello con questa:
# Inizializzazione pulita per evitare il conflitto 'inter_threads'
model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
    cpu_threads=1,        # Essenziale per evitare il crash del vettore C++ su Jetson
    num_workers=1
)

def svuota_seriale():
    t0 = time.time()
    while time.time() - t0 < 0.05 and arduino.in_waiting:
        _ = arduino.readline()

def invia_e_attendi(cmd: str):
    svuota_seriale()
    arduino.write((cmd + "\n").encode())
    print(f"   [JETSON] Inviato: {cmd}")

    deadline = time.time() + ACK_TIMEOUT_S
    while time.time() < deadline:
        if arduino.in_waiting:
            r = arduino.readline().decode("utf-8", errors="ignore").strip()
            if ">>> ACK:" in r:
                print(f"   [ARDUINO] {r}")
                return True
        else:
            time.sleep(0.01)

    print("   [WARN] ACK non ricevuto (timeout)")
    return False

def energia_media(data_bytes: bytes) -> float:
    x = np.frombuffer(data_bytes, dtype=np.int16)
    x = x.reshape(-1, 2)
    eL = np.abs(x[:, 0]).mean()
    eR = np.abs(x[:, 1]).mean()
    return float(max(eL, eR))

def bytes_to_mono_float32(data_bytes: bytes) -> np.ndarray:
    x = np.frombuffer(data_bytes, dtype=np.int16).reshape(-1, 2).astype(np.float32)
    mono = 0.5 * (x[:, 0] + x[:, 1])
    return mono / 32768.0

def resample_linear(x: np.ndarray, in_rate: int, out_rate: int) -> np.ndarray:
    if in_rate == out_rate:
        return x
    n_in = x.shape[0]
    n_out = int(n_in * (out_rate / in_rate))
    if n_out <= 0:
        return np.zeros((0,), dtype=np.float32)
    t_in = np.linspace(0.0, 1.0, num=n_in, endpoint=False, dtype=np.float32)
    t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False, dtype=np.float32)
    return np.interp(t_out, t_in, x).astype(np.float32)

def normalize_rms(x: np.ndarray, target_rms: float = 0.08) -> np.ndarray:
    rms = float(np.sqrt(np.mean(x * x) + 1e-12))
    if rms < 1e-5:
        return x
    gain = min(target_rms / rms, 6.0)
    y = x * gain
    return np.clip(y, -1.0, 1.0)

def ascolta_vad(stream) -> str:
    pre_roll = []
    frames = []
    triggered = False
    above = 0
    silence = 0

    max_frames = int((INPUT_RATE * MAX_RECORD_SECONDS) / CHUNK)
    min_frames = int((INPUT_RATE * MIN_RECORD_SECONDS) / CHUNK)

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        e = energia_media(data)

        pre_roll.append(data)
        if len(pre_roll) > PRE_ROLL_FRAMES:
            pre_roll.pop(0)

        if not triggered:
            if e >= SOGLIA_VOL:
                above += 1
                if above >= START_FRAMES:
                    triggered = True
                    frames.extend(pre_roll)
                    frames.append(data)
                    silence = 0
            else:
                above = 0
        else:
            frames.append(data)
            silence = silence + 1 if e < SOGLIA_VOL else 0

            if len(frames) >= min_frames and (silence >= SILENCE_FRAMES or len(frames) >= max_frames):
                break
            if len(frames) >= max_frames:
                break

    if not frames:
        return ""

    audio = bytes_to_mono_float32(b"".join(frames))
    audio_16k = resample_linear(audio, INPUT_RATE, WHISPER_RATE)
    audio_16k = normalize_rms(audio_16k)

    init_prompt = (
        "Comandi vocali per una mano robotica: "
        "apri la mano, chiudi la mano, apri il pollice, chiudi l'indice, stop."
    )

    segments, _ = model.transcribe(
        audio_16k,
        language="it",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=init_prompt
    )
    return " ".join(s.text for s in segments).strip().lower()

def fuzzy_contains(text: str, variants):
    t = text.replace("'", " ").replace(".", " ").replace(",", " ")
    return any(v in t for v in variants)

def interpreta(testo: str):
    if not testo:
        return

    if fuzzy_contains(testo, ["stop", "smetti", "basta", "dolore", "ferma"]):
        invia_e_attendi("stop")
        return

    dita = {"mignolo": "1", "anulare": "2", "medio": "3", "indice": "4", "pollice": "5"}

    chiudi_variants = ["chiudi", "chiud", "stringi", "chiudere", "chiùdi"]
    apri_variants   = ["apri", "apr", "a pre", "appi", "abre", "apre", "aprire", "molla", "rilassa", "lascia"]

    if fuzzy_contains(testo, chiudi_variants):
        act = "on"
    elif fuzzy_contains(testo, apri_variants):
        act = "off"
    else:
        return

    if fuzzy_contains(testo, ["mano", "tutto", "tutte", "pugno"]):
        invia_e_attendi("allon" if act == "on" else "alloff")
        return

    for nome, num in dita.items():
        if nome in testo:
            invia_e_attendi(f"{num}{act}")

def main():
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=INPUT_RATE,
        input=True,
        input_device_index=MIC_ID,
        frames_per_buffer=CHUNK
    )

    print("\n--- ASCOLTO CONTINUO (VAD) ---")
    try:
        while True:
            if arduino.in_waiting:
                line = arduino.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("P:"):
                    print(f"\r{line}      ", end="")

            cmd = ascolta_vad(stream)
            if cmd:
                print(f"\nVoce: '{cmd}'")
                interpreta(cmd)

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        arduino.close()

if __name__ == "__main__":
    main()