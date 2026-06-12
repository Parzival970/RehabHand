# Crea un file chiamato check_audio.py e lancialo
import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    print(f"ID {i}: {p.get_device_info_by_index(i).get('name')}")
p.terminate()