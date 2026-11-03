// Respira +: firmware de la máscara (ESP32 + sensor MQ-7).
//
// Qué hace:
//  1. Lee el MQ-7 cada 2 segundos y calcula los ppm de CO.
//  2. Activa la alarma LOCAL (LED y buzzer) según los umbrales. No depende de internet.
//  3. Guarda cada lectura en memoria. Si hay Wi-Fi, envía lotes a la API con el token.
//     Si no hay Wi-Fi, las lecturas se acumulan y se envían cuando vuelve la conexión.
//
// Comandos por el monitor serie (115200 baudios):
//  c : calibrar R0 con el sensor en aire limpio (espere 3 minutos de calentamiento antes)
//  s : mostrar estado (Wi-Fi, buffer, último valor)

#include <Arduino.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <math.h>
#include <time.h>

#include "config.h"

// ---------- Pines ----------
constexpr int PIN_MQ7 = 34;     // entrada analógica (solo entrada, ADC1)
constexpr int PIN_BUZZER = 25;  // buzzer activo o pasivo
constexpr int PIN_LED = 26;     // LED rojo con resistencia de 220 ohm

// Divisor de tensión entre la salida del MQ-7 y el pin del ESP32.
// 10 kohm arriba y 15 kohm abajo: Vadc = Vsalida * 15 / 25 = 0,6 * Vsalida.
// Así, 5 V llegan como 3 V, dentro del límite de 3,3 V del ESP32.
constexpr float DIVIDER = 0.6f;

// ---------- Tiempos y tamaños ----------
constexpr uint32_t SAMPLE_MS = 2000;
constexpr uint32_t SEND_EVERY_MS = 10000;
constexpr size_t BUFFER_SIZE = 200;
constexpr size_t BATCH_MAX = 20;

// Modelo aproximado de sensibilidad del MQ-7 (curva de la hoja de datos, aproximada).
constexpr float CURVE_A = 22.073f;
constexpr float CURVE_B = 0.66659f;

struct Lectura {
  uint32_t seq;
  int64_t epoch;   // 0 si la hora no está sincronizada
  float ppm;
  bool alarma;
};

// ---------- Estado ----------
Lectura buffer[BUFFER_SIZE];
size_t bufHead = 0;   // próximo lugar para escribir
size_t bufCount = 0;  // lecturas pendientes de enviar
uint32_t seqActual = 0;
uint32_t bootId = 0;
uint32_t ultimoEnvio = 0;
uint32_t ultimaLectura = 0;
uint32_t arranque = 0;
uint32_t proximoIntento = 0;
uint32_t esperaReintento = 2000;
float ultimoPpm = 0;
bool horaSincronizada = false;

Preferences prefs;

// ---------- Sensor ----------

float leerVoltajeSalida() {
  // Promedio de 16 muestras para reducir ruido.
  uint32_t mv = 0;
  for (int i = 0; i < 16; i++) mv += analogReadMilliVolts(PIN_MQ7);
  float vadc = (mv / 16.0f) / 1000.0f;
  return vadc / DIVIDER;  // voltaje real de salida del módulo
}

float resistenciaSensor(float vSalida) {
  // Rs = RL * (Vc - Vsalida) / Vsalida. Resultado en kohm.
  if (vSalida < 0.02f) return NAN;  // salida en cero: sensor desconectado o sin alimentar
  return RL_KOHM * (VC_VOLTS - vSalida) / vSalida;
}

float leerCO() {
#if SIMULATE_SENSOR
  // Triángulo de 0 a 80 ppm y de vuelta, cada 2 minutos. Sirve para probar alarmas sin gas.
  static uint32_t paso = 0;
  paso++;
  float fase = fabsf(fmodf((float)paso / 60.0f, 2.0f) - 1.0f);  // 1 -> 0 -> 1
  return 80.0f * (1.0f - fase);
#else
  float rs = resistenciaSensor(leerVoltajeSalida());
  if (isnan(rs)) return NAN;
  float ratio = rs / R0_KOHM;  // Rs/R0
  // Invertir la curva: ratio = A * ppm^(-B)  =>  ppm = (ratio/A)^(-1/B)
  float ppm = powf(ratio / CURVE_A, -1.0f / CURVE_B);
  if (ppm < 0) ppm = 0;
  if (ppm > 1000) ppm = 1000;
  return ppm;
#endif
}

// ---------- Alarma local ----------

void actualizarAlarma(float ppm) {
  bool critica = ppm >= ALARMA_CRITICA_PPM;
  bool aviso = ppm >= ALARMA_AVISO_PPM;
  if (critica) {
    digitalWrite(PIN_LED, HIGH);
    tone(PIN_BUZZER, 2500);
  } else if (aviso) {
    // Parpadeo lento para aviso.
    bool encendido = (millis() / 400) % 2 == 0;
    digitalWrite(PIN_LED, encendido);
    if (encendido) tone(PIN_BUZZER, 1800); else noTone(PIN_BUZZER);
  } else {
    digitalWrite(PIN_LED, LOW);
    noTone(PIN_BUZZER);
  }
}

// ---------- Buffer ----------

void guardarLectura(float ppm) {
  Lectura l;
  l.seq = ++seqActual;
  time_t ahora = time(nullptr);
  l.epoch = (horaSincronizada && ahora > 1700000000) ? (int64_t)ahora : 0;
  l.ppm = ppm;
  l.alarma = ppm >= ALARMA_AVISO_PPM;

  buffer[bufHead] = l;
  bufHead = (bufHead + 1) % BUFFER_SIZE;
  if (bufCount < BUFFER_SIZE) {
    bufCount++;
  }
  // Si el buffer está lleno, la lectura nueva reemplaza a la más vieja (se pierde la más antigua).
}

// Índice del elemento i-ésimo pendiente (0 = el más viejo).
size_t indicePendiente(size_t i) {
  size_t inicio = (bufHead + BUFFER_SIZE - bufCount) % BUFFER_SIZE;
  return (inicio + i) % BUFFER_SIZE;
}

void descartarPendientes(size_t n) {
  if (n > bufCount) n = bufCount;
  bufCount -= n;
}

// ---------- Red ----------

void conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("Conectando a Wi-Fi %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Wi-Fi conectado. IP %s\n", WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    time_t t = 0;
    for (int i = 0; i < 20 && t < 1700000000; i++) {
      delay(500);
      t = time(nullptr);
    }
    horaSincronizada = t > 1700000000;
    Serial.println(horaSincronizada ? "Hora sincronizada por NTP." : "Sin hora NTP: se enviará epoch null.");
  } else {
    Serial.println("Sin Wi-Fi por ahora. Las lecturas se guardan en memoria.");
  }
}

// Devuelve el código HTTP, o -1 si no hubo respuesta.
int enviarLote(size_t cantidad) {
  // Construir el JSON del contrato (ver docs/guia/02-arquitectura.md, sección 7).
  String body;
  body.reserve(256 + cantidad * 240);
  body += "{\"dispositivo\":\"";
  body += DEVICE_CODE;
  body += "\",\"boot_id\":";
  body += String(bootId);
  if (strlen(BRIGADISTA) > 0) {
    body += ",\"brigadista\":\"";
    body += BRIGADISTA;
    body += "\"";
  } else {
    body += ",\"brigadista\":null";
  }
  body += ",\"lote\":[";
  for (size_t i = 0; i < cantidad; i++) {
    const Lectura& l = buffer[indicePendiente(i)];
    if (i > 0) body += ",";
    char epoch[24];
    if (l.epoch == 0) {
      snprintf(epoch, sizeof(epoch), "null");
    } else {
      snprintf(epoch, sizeof(epoch), "%lld", (long long)l.epoch);
    }
    char item[280];
    snprintf(item, sizeof(item),
             "{\"seq\":%lu,\"epoch_s\":%s,\"co_ppm\":%.2f,\"o2_pct\":null,"
             "\"presion_bar\":null,\"filtro_ok\":null,\"bateria_pct\":null,"
             "\"alarma_local\":%s,\"lat\":null,\"lon\":null}",
             (unsigned long)l.seq, epoch, l.ppm, l.alarma ? "true" : "false");
    body += item;
  }
  body += "]}";

  WiFiClientSecure cliente;
  cliente.setCACert(ROOT_CA_PEM);
  HTTPClient http;
  String url = String("https://") + API_HOST + API_PATH;
  if (!http.begin(cliente, url)) return -1;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  http.setTimeout(15000);
  int codigo = http.POST(body);
  if (codigo > 0) {
    Serial.printf("Lote de %u enviado: HTTP %d\n", (unsigned)cantidad, codigo);
    if (codigo != 200) Serial.println(http.getString());
  } else {
    Serial.printf("Fallo de red al enviar: %s\n", http.errorToString(codigo).c_str());
  }
  http.end();
  return codigo;
}

void intentarEnviar() {
  if (bufCount == 0) return;
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() < proximoIntento) return;

  size_t cantidad = bufCount < BATCH_MAX ? bufCount : BATCH_MAX;
  int codigo = enviarLote(cantidad);

  if (codigo == 200) {
    descartarPendientes(cantidad);
    esperaReintento = 2000;
    ultimoEnvio = millis();
  } else if (codigo == 401 || codigo == 422) {
    // Error permanente: el token o el brigadista no sirven. Reintentar no ayuda.
    Serial.println("Lote rechazado por la API (token o brigadista). Se descarta.");
    descartarPendientes(cantidad);
    esperaReintento = 2000;
  } else {
    // Error temporal (red, servicio dormido, 5xx): reintentar con espera creciente.
    proximoIntento = millis() + esperaReintento;
    esperaReintento = (esperaReintento * 2 > 60000) ? 60000 : esperaReintento * 2;
  }
}

// ---------- Calibración ----------

void calibrarR0() {
  Serial.println("Calibrando R0 en aire limpio. Mantenga el sensor en aire fresco, sin humo, 60 segundos...");
  double suma = 0;
  int n = 0;
  for (int i = 0; i < 60; i++) {
    float rs = resistenciaSensor(leerVoltajeSalida());
    if (!isnan(rs)) {
      suma += rs;
      n++;
    }
    delay(1000);
  }
  if (n == 0) {
    Serial.println("No se pudo leer el sensor. Revise las conexiones.");
    return;
  }
  float rsAire = suma / n;
  float r0 = rsAire / CLEAN_AIR_FACTOR;
  Serial.printf("Rs en aire limpio: %.2f kohm\n", rsAire);
  Serial.printf("R0 sugerido: %.2f kohm. Copie este valor en R0_KOHM de config.h.\n", r0);
}

void revisarSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'c') calibrarR0();
    if (c == 's') {
      Serial.printf("Wi-Fi: %s | pendientes: %u | último: %.2f ppm | boot %lu\n",
                    WiFi.status() == WL_CONNECTED ? "conectado" : "sin conexión",
                    (unsigned)bufCount, ultimoPpm, (unsigned long)bootId);
    }
  }
}

// ---------- Programa principal ----------

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nRespira + firmware iniciando");

  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  analogReadResolution(12);
  analogSetPinAttenuation(PIN_MQ7, ADC_11db);  // rango de 0 a unos 3,1 V

  // Número de arranque, guardado en memoria no volátil.
  prefs.begin("respira", false);
  bootId = prefs.getUInt("boot", 0) + 1;
  prefs.putUInt("boot", bootId);

  arranque = millis();
  Serial.printf("Modo: %s. Boot %lu. Calentamiento de %d s antes de enviar.\n",
                SIMULATE_SENSOR ? "SIMULADO" : "sensor real", (unsigned long)bootId, WARMUP_SECONDS);
  conectarWifi();
}

void loop() {
  revisarSerie();

  if (WiFi.status() != WL_CONNECTED) {
    static uint32_t ultimoIntentoWifi = 0;
    if (millis() - ultimoIntentoWifi > 15000) {
      ultimoIntentoWifi = millis();
      conectarWifi();
    }
  }

  if (millis() - ultimaLectura >= SAMPLE_MS) {
    ultimaLectura = millis();
    float ppm = leerCO();
    if (!isnan(ppm)) {
      ultimoPpm = ppm;
      actualizarAlarma(ppm);  // la alarma local siempre funciona, con o sin red
      bool calentado = (millis() - arranque) >= (uint32_t)WARMUP_SECONDS * 1000UL;
      if (calentado) guardarLectura(ppm);
      Serial.printf("CO: %.1f ppm%s\n", ppm, calentado ? "" : " (calentando, no se envía)");
    } else {
      Serial.println("Sensor sin lectura: revise el cableado del MQ-7.");
    }
  }

  bool hayPendientes = bufCount > 0;
  bool loLleno = bufCount >= BATCH_MAX;
  bool tocaEnviar = millis() - ultimoEnvio >= SEND_EVERY_MS;
  if (hayPendientes && (loLleno || tocaEnviar)) {
    intentarEnviar();
  }

  delay(20);
}
