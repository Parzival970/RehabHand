// ===================== PINS & CONFIG =====================
[cite_start]// Mappatura valvole: 1=mignolo, 2=anulare, 3=medio, 4=indice, 5=pollice [cite: 1]
const int VALVE_PINS[5] = { 11, 10, 6, 5, 3 }; 
const int PRESS_PIN = A0; [cite_start]// Sensore di pressione su A0 [cite: 2]

[cite_start]// Calibrazione sensore (P[kPa] = m*V + q) [cite: 4, 5]
const int   ADC_MAX = 1023; [cite_start]// Risoluzione 10-bit standard [cite: 3]
const float VREF    = 5.0;  [cite_start]// Tensione di riferimento [cite: 3]
const float M_KPA_PER_V = 112.7352; 
const float Q_KPA       = -54.9085; 

unsigned long logPeriodMs = 200; [cite_start]// Frequenza log [cite: 6]
unsigned long lastLog = 0;

enum Mode { VENT = 0, FEED = 1 }; 
Mode modes[5] = { VENT, VENT, VENT, VENT, VENT }; 

// Se HIGH deve gonfiare, imposta true. [cite_start]Se LOW deve gonfiare, imposta false. [cite: 7]
bool COIL_ON_MEANS_FEED[5] = { true, true, true, true, true }; 

// ===================== FUNZIONI DI LOGICA =====================

float readPressure_kPa() {
  int raw = analogRead(PRESS_PIN);
  float voltage = (raw * VREF) / ADC_MAX;
  return M_KPA_PER_V * voltage + Q_KPA; [cite_start]// [cite: 11]
}

void applyValveState(int idx) {
  bool coilOnMeansFeed = COIL_ON_MEANS_FEED[idx];
  Mode m = modes[idx];
  [cite_start]// Calcola se il pin deve essere HIGH o LOW in base alla logica della valvola [cite: 12, 13]
  bool coilOn = (m == FEED) ? coilOnMeansFeed : !coilOnMeansFeed;
  digitalWrite(VALVE_PINS[idx], coilOn ? HIGH : LOW);
}

const char* fingerName(int idx) {
  switch (idx) {
    case 0: return "MIGNOLO"; case 1: return "ANULARE";
    case 2: return "MEDIO";   case 3: return "INDICE"; 
    case 4: return "POLLICE"; default: return "UNKNOWN";
  }
}

void setMode(int idx, Mode m) {
  if (idx < 0 || idx > 4) return;
  modes[idx] = m;
  applyValveState(idx);
  // Feedback per la Jetson
  Serial.print(">>> ACK: "); Serial.print(fingerName(idx));
  Serial.println(m == FEED ? " -> FEED (ON)" : " -> VENT (OFF)");
}

void setAll(Mode m) {
  for (int i = 0; i < 5; i++) {
    modes[i] = m;
    applyValveState(i);
  }
  Serial.println(m == FEED ? ">>> ACK: ALL FEED" : ">>> ACK: ALL VENT");
}

// ===================== GESTIONE SERIALE =====================

void handleSerial() {
  if (!Serial.available()) return;
  String cmd = Serial.readStringUntil('\n'); [cite_start]// [cite: 36]
  cmd.trim();
  cmd.toLowerCase();
  
  if (cmd.length() == 0) return;

  // Comando di emergenza vocale (prioritario)
  if (cmd == "stop" || cmd == "smetti" || cmd == "alloff") {
    setAll(VENT);
    Serial.println(">>> ACK: EMERGENCY STOP EXECUTED");
    return;
  }

  if (cmd == "allon") {
    setAll(FEED);
    return;
  }

  [cite_start]// Comandi dita singole (es. 1on, 5off) [cite: 37, 38]
  if (cmd.length() >= 3 && isDigit(cmd.charAt(0))) {
    int n = cmd.charAt(0) - '0';
    int idx = n - 1; [cite_start]// [cite: 38]
    String tail = cmd.substring(1);
    
    if (tail == "on")       { setMode(idx, FEED); [cite_start]} // [cite: 39]
    else if (tail == "off") { setMode(idx, VENT); [cite_start]} // [cite: 40]
  }
}

void setup() {
  [cite_start]// Configurazione pin valvole come output [cite: 56]
  for (int i = 0; i < 5; i++) {
    pinMode(VALVE_PINS[i], OUTPUT);
  }
  
  setAll(VENT); [cite_start]// Stato iniziale di sicurezza: sfiato [cite: 57, 58]
  
  Serial.begin(115200);
  while (!Serial) { ; } // Attesa connessione USB (necessario su R4)
}

void loop() {
  handleSerial(); [cite_start]// [cite: 59]

  [cite_start]// Invio periodico della pressione alla Jetson [cite: 59]
  unsigned long now = millis();
  if (now - lastLog >= logPeriodMs) {
    lastLog = now;
    Serial.print("P:"); 
    Serial.print(readPressure_kPa(), 1); 
    Serial.println(" kPa");
  }
}