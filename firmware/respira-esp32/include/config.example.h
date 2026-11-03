// Configuración del firmware de Respira +.
// Copiar este archivo a include/config.h y completar los valores.
// include/config.h NO se sube a GitHub (está en .gitignore).

#pragma once

// ---- Wi-Fi ----
#define WIFI_SSID      "NOMBRE_DE_TU_RED"
#define WIFI_PASSWORD  "CLAVE_DE_TU_RED"

// ---- Servicio de ingesta ----
#define API_HOST       "respira-ingesta.onrender.com"
#define API_PATH       "/v1/lecturas"

// ---- Identidad de la máscara (los entrega el registro en la base) ----
#define DEVICE_CODE    "RESP-0001"
#define DEVICE_TOKEN   "PEGAR_AQUI_EL_TOKEN_DE_LA_MASCARA"
#define BRIGADISTA     "B-017"   // seudónimo; "" para no asignar

// ---- Modo de prueba ----
// 1 = genera valores de CO simulados (sin sensor). Úselo para probar Wi-Fi y la API.
// 0 = lee el sensor MQ-7 real.
#define SIMULATE_SENSOR 1

// ---- Calibración del MQ-7 (ver docs/guia/08-esp32-mq7.md) ----
#define RL_KOHM        10.0f    // resistencia de carga del módulo (revisar la placa)
#define VC_VOLTS       5.0f     // tensión real de alimentación del módulo
#define R0_KOHM        10.0f    // placeholder: calibrar en aire limpio
#define CLEAN_AIR_FACTOR 26.09f // constante aproximada para aire limpio (ver guía)

// ---- Umbrales de alarma local (deben coincidir con ingesta/app/reglas.py) ----
#define ALARMA_AVISO_PPM   35.0f
#define ALARMA_CRITICA_PPM 200.0f

// ---- Tiempo de calentamiento antes de enviar datos reales ----
#define WARMUP_SECONDS 180

// Certificado raíz que firma el HTTPS de Render (GTS Root R4, válido hasta 2036).
static const char ROOT_CA_PEM[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIICCTCCAY6gAwIBAgINAgPlwGjvYxqccpBQUjAKBggqhkjOPQQDAzBHMQswCQYD
VQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEUMBIG
A1UEAxMLR1RTIFJvb3QgUjQwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAwMDAw
WjBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2Vz
IExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjQwdjAQBgcqhkjOPQIBBgUrgQQAIgNi
AATzdHOnaItgrkO4NcWBMHtLSZ37wWHO5t5GvWvVYRg1rkDdc/eJkTBa6zzuhXyi
QHY7qca4R9gq55KRanPpsXI5nymfopjTX15YhmUPoYRlBtHci8nHc8iMai/lxKvR
HYqjQjBAMA4GA1UdDwEB/wQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQW
BBSATNbrdP9JNqPV2Py1PsVq8JQdjDAKBggqhkjOPQQDAwNpADBmAjEA6ED/g94D
9J+uHXqnLrmvT/aDHQ4thQEd0dlq7A/Cr8deVl5c1RxYIigL9zC2L7F8AjEA8GE8
p/SgguMh1YQdc4acLa/KNJvxn7kjNuK8YAOdgLOaVsjh4rsUecrNIdSUtUlD
-----END CERTIFICATE-----
)EOF";
