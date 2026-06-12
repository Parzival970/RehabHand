import torch
import matplotlib.pyplot as plt
import numpy as np

# 1. Verifica se la GPU (CUDA) è disponibile
print("--- TEST HARDWARE ---")
if torch.cuda.is_value_available() or torch.cuda.is_available():
    print(f"✅ GPU rilevata: {torch.cuda.get_device_name(0)}")
    print(f"Memoria GPU totale: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
else:
    print("❌ GPU NON rilevata. Sistema in modalità CPU.")

# 2. Test Grafico (per vedere se VcXsrv riceve il segnale)
print("\n--- TEST GRAFICO ---")
print("Sto aprendo una finestra sul tuo Surface...")

t = np.arange(0.0, 2.0, 0.01)
s = 1 + np.sin(2 * np.pi * t)

plt.plot(t, s)
plt.title('Test Grafico dalla Jetson!')
plt.grid(True)
plt.show()