# Respira +: diseño del MVP de telemetría y base de datos

Fecha: 2026-11-03
Estado: borrador para aprobación
Proyecto: Taller Complejo, UAI (Respira +, protección respiratoria para brigadistas CONAF)

## 1. Intención y motivo

La máscara mide monóxido de carbono (CO) mientras el brigadista combate un incendio. Hoy la exposición no queda registrada ni llega a la central, así que nadie puede ver en tiempo real qué le pasa a cada brigadista ni decidir el retiro a tiempo. El MVP debe lograr que cada lectura de la máscara quede guardada en una base de datos en la nube, sin costo, y que la central pueda ver el estado y recibir avisos.

El éxito del MVP es este: un ESP32 con sensor de CO envía lecturas a la base de datos, las lecturas sobreviven a cortes de red, un supervisor recibe una alerta cuando el CO supera un umbral y existe un registro consultable de cada sesión.

## 2. Objetivos

- O1. El ESP32 envía lecturas de CO, estado de alarma y batería a una base de datos PostgreSQL alojada en un servicio gratuito.
- O2. Ninguna lectura se pierde por un corte de red: el dispositivo guarda en buffer local y reenvía; el servidor descarta duplicados.
- O3. Al cruzar un umbral de CO, el sistema envía una alerta a un supervisor (Telegram).
- O4. Si un dispositivo deja de reportar, el sistema lo marca como "sin señal" después de un tiempo definido.
- O5. Existe un simulador que genera lecturas con el mismo formato del ESP32, para probar la base de datos sin hardware.
- O6. (Posterior al MVP inicial) Un dashboard web muestra el estado de cada brigadista y el historial de sesiones.

## 3. No objetivos

- No reemplaza la alarma local. La máscara debe sonar con buzzer y LED aunque no haya red.
- No controla válvulas, cilindro de aire ni oxígeno desde la nube.
- No es un dispositivo certificado de protección personal. Cualquier uso real requiere validación del fabricante y de prevención de riesgos.
- No cumple por sí mismo con la normativa de datos personales. Solo deja la base lista para revisarla.
- GPS es opcional en el MVP.

## 4. Antimetas (si ocurre esto, el MVP fracasó aunque funcione técnicamente)

- Que la alarma dependa de la red o de la base de datos.
- Que un dispositivo deje de enviar y nadie se entere (silencio sin alerta).
- Que el nombre real del brigadista quede junto a sus datos de salud dentro de la misma base.
- Que la base acepte escrituras de cualquiera que conozca la URL.

## 5. Restricciones

- Costo cero en el MVP. Se usan planes gratuitos y se documenta el límite de cada uno.
- Hardware: ESP32 (Wi-Fi, sin módulo celular en el MVP). Sensor de CO: MQ-7 (confirmado por la persona a cargo).
  - El MQ-7 es un sensor semiconductor (óxido metálico), no electroquímico. Entrega voltaje analógico, no ppm. Responde también a otros gases (hidrógeno, alcohol), tiene deriva con la temperatura y la humedad, y necesita un ciclo de calentamiento (en la hoja de datos típica: 5 V durante 60 s y 1,4 V durante 90 s; verificar con el módulo). Su precisión es insuficiente para una alarma de seguridad sin calibración en terreno.
  - Por eso el MVP lo usa solo para prototipo. Antes de cualquier uso con personas se debe evaluar un sensor electroquímico de CO, que tiene mejor respuesta lineal y selectividad.
  - El ESP32 lee la salida con el ADC, que admite hasta 3,3 V. El MQ-7 entrega hasta 5 V, así que la salida pasa por un divisor de tensión.
- Conectividad en terreno: intermitente. Para el MVP se asume un hotspot de teléfono o de vehículo.
- Datos de salud: la información de exposición es sensible. Se guarda solo un seudónimo del brigadista.

## 6. Arquitectura elegida

Flujo general, por capas:

1. Dispositivo (ESP32). Lee el sensor de CO, calcula el estado y activa la alarma local. Guarda cada lectura en una cola local (memoria flash o tarjeta SD). Cuando hay Wi-Fi, envía lotes de lecturas.
2. Servicio de ingesta. Una API pequeña en Python (FastAPI) que recibe lotes por HTTPS, valida el token del dispositivo, inserta las lecturas sin duplicar y evalúa los umbrales.
3. Base de datos. PostgreSQL gratuito (Supabase en el plan free). Solo el servicio de ingesta escribe en ella.
4. Alertas. El mismo servicio de ingesta envía mensajes a un bot de Telegram cuando se cruza un umbral o hay silencio.
5. Dashboard (posterior). Grafana Cloud o una página en Next.js que lee la base.

Decisiones de este diseño (mías, para revisar):

- D1. Envío por HTTPS en lotes, no por MQTT. Usa menos servicios y es más fácil de depurar. MQTT (por ejemplo HiveMQ Cloud gratuito) se evalúa si se necesita latencia menor a unos segundos.
- D2. El servicio de ingesta corre en un servicio gratuito de contenedores (Render o Google Cloud Run en plan free). Como estos planes pueden dormirse, el dispositivo reintenta y el buffer evita pérdidas. Si el arranque en frío molesta, se cambia de proveedor sin tocar la base.
- D3. La base es Postgres estándar. Si Supabase deja de convenir, se migra a Neon u otro Postgres sin reescribir el esquema.
- D4. El dispositivo no se conecta a la base directamente. Así no se expone ninguna credencial de la base dentro del ESP32.

## 7. Modelo de datos (PostgreSQL)

Tablas:

- brigadistas: id (uuid), seudonimo (texto único), activo (bool). No guarda nombre ni RUT.
- dispositivos: id (uuid), codigo (texto único, impreso en la máscara), token_hash (texto), version_firmware, creado_en.
- sesiones: id (uuid), dispositivo_id, brigadista_id, inicio, fin (nulo mientras está activa), incidente (texto, opcional).
- lecturas: id (bigserial), dispositivo_id, sesion_id (nulo si no hay sesión), seq (entero que crece en el dispositivo), ts_dispositivo (nulo si el reloj no está sincronizado), ts_recepcion, co_ppm (numérico), o2_pct (nulo si no hay sensor), presion_bar (nulo si no hay sensor), filtro_ok (bool, nulo si no hay sensor), bateria_pct, alarma_local (bool), lat y lon (nulos).
  - Restricción única: (dispositivo_id, boot_id, seq). Así un reenvío no duplica filas, y un reinicio del ESP32 no descarta lecturas nuevas aunque el contador vuelva a cero.
  - boot_id: número que el dispositivo incrementa en flash en cada arranque. El contador seq también se guarda en flash.
- alertas: id, sesion_id, tipo (CO_ALTO, O2_BAJO, PRESION_BAJA, BATERIA_BAJA, SIN_SEÑAL), nivel (AVISO, CRITICA), valor, umbral, creada_en, reconocida_en (nulo), reconocida_por (texto).
- umbrales: tipo, nivel, valor, vigente (bool). En la versión construida es solo referencia: las reglas que usa el código están en ingesta/app/reglas.py. Para cambiar un umbral hoy hay que editar ese archivo. Pasar los umbrales a la base queda pendiente.

Vista:

- ultimo_estado: última lectura por dispositivo, con sesión activa y brigadista asociado.

## 8. Umbrales de partida (propuestos, validar antes de usar)

Son valores de referencia para el prototipo. No deben tomarse como definitivos.

- CO aviso: 35 ppm (referencia NIOSH de exposición promedio de 10 horas).
- CO crítico: 200 ppm (propuesta mía; por debajo de 1200 ppm, que es el valor IDLH de NIOSH).
- O2 bajo: 19,5 %.
- Presión de cilindro baja: 50 bar (propuesta mía).
- Batería baja: 20 %.
- Sin señal: 60 segundos sin lecturas en una sesión activa.

Antes de usarlos se deben confirmar con prevención de riesgos y con la normativa chilena vigente.

## 9. Contrato de ingesta

Ruta: POST /v1/lecturas
Encabezado: X-Device-Token: <token del dispositivo>
Cuerpo (JSON):

    {
      "dispositivo": "RESP-0001",
      "boot_id": 7,
      "brigadista": "B-017",
      "lote": [
        {
          "seq": 1042,
          "epoch_s": 1793731200,
          "co_ppm": 12.4,
          "o2_pct": 20.8,
          "presion_bar": 212.0,
          "filtro_ok": true,
          "bateria_pct": 87,
          "alarma_local": false,
          "lat": null,
          "lon": null
        }
      ]
    }

Respuesta: 200 con el último seq aceptado. Las repeticiones se aceptan y se ignoran sin error.

Decisiones: el dispositivo envía epoch_s solo si ya sincronizó la hora por NTP; si no, envía null y el servidor usa ts_recepcion. Los campos de sensores opcionales van en null cuando el hardware no los tiene.

## 10. Seguridad mínima

- Token por dispositivo, generado al registrarlo. La base guarda solo el hash.
- HTTPS obligatorio.
- En Supabase, Row Level Security activado en todas las tablas. El servicio de ingesta usa una credencial de servidor, nunca expuesta al dispositivo ni al navegador.
- Sin nombres reales en la base. La relación seudónimo y persona vive fuera de la base, en un registro aparte con acceso restringido.

## 11. Plan de construcción (después de aprobar este documento)

Fase 1, lo que se pidió primero: esquema SQL, prueba con PostgreSQL local, servicio de ingesta con pruebas automáticas y simulador en Python que envía lotes con el contrato de la sección 9.
Fase 2: firmware del ESP32 con buffer local, reenvío y alarma local.
Fase 3: alertas por Telegram y detección de "sin señal".
Fase 4: dashboard web.

Pruebas de la fase 1: insertar lotes repetidos no duplica filas, un lote con un campo faltante se rechaza con mensaje claro, el umbral de CO genera una alerta una sola vez por cruce.

## 12. Lo que queda para el constructor

- Calibración del MQ-7: valor R0 en aire limpio y curva Rs/R0 contra ppm de CO, medida contra un gas de referencia. Sin esto, el campo co_ppm del contrato no es confiable. La calibración debe documentarse por dispositivo.
  - Las fuentes no coinciden en la concentración de referencia para R0 (100 ppm en la hoja de Hanwei, 1000 ppm en la de Joy-IT). Se debe fijar una y documentarla.
  - La curva Rs/R0 = 22,073 por ppm elevado a -0,66659 que circula en proyectos de Arduino es una aproximación a 20 °C y 65 % HR, no un dato de fábrica. Sirve para prototipo, no para una alarma.
  - La resistencia de carga mínima recomendada es de 5 kΩ. Temperatura y humedad afectan la lectura, así que la compensación debe considerarse.
  - El MQ-7B (Winsen) usa 1,5 V en la fase baja, no 1,4 V. No mezclar hojas de datos.
  - Ciclo de calentamiento: 5 V por 60 s y 1,4 V por 90 s según la hoja de datos típica. Un proveedor indica que su módulo funciona a 5 V fijo, así que cada módulo debe verificarse.
- Forma de registrar dispositivos y brigadistas (hoy se asume carga manual).
- Qué tan larga puede ser la cola local antes de descartar datos viejos.

## 13. Decisiones que tomé por defecto (para revisar)

- Supabase como base, FastAPI como servicio de ingesta, Telegram para alertas.
- HTTPS en lotes en vez de MQTT.
- Solo seudónimo en la base.
- Umbrales de la sección 8.

## 14. Decisiones tomadas tras la revisión del constructor (mías, para revisar)

- Sesiones. La máscara lleva el código del brigadista (campo "brigadista" del lote), asignado al encenderla con un código impreso o con un selector simple. El servidor abre una sesión la primera vez que ve ese brigadista en un dispositivo y la cierra tras 15 minutos sin lecturas o cuando el dispositivo envía fin de sesión. Las lecturas sin brigadista quedan con sesion_id nulo y generan alerta de "sin asignar".
- Detección de silencio. La revisión la hace pg_cron dentro de Supabase cada minuto, así no depende de que el servicio de ingesta esté despierto. Riesgo conocido: el plan gratuito de Supabase pausa proyectos inactivos; el dispositivo envía un latido cada 30 segundos cuando tiene red para evitarlo.
- Reinicios del ESP32. seq y boot_id se guardan en flash (NVS). La clave única incluye boot_id (sección 7).
- Histéresis y reenvío de alertas. Una alerta de CO se crea al cruzar el umbral. Se vuelve a armar solo cuando el valor baja del 90 % del umbral. Mientras siga sobre el umbral, se repite como máximo cada 60 segundos. Pasar de AVISO a CRITICA crea una alerta nueva.
- Cola local. El dispositivo guarda hasta 24 horas de lecturas (en SD). Si se llena, descarta primero las lecturas de aviso y conserva las críticas.

Pendientes que dependen de la persona a cargo (no están resueltos):

- Destinatarios de las alertas de Telegram y quién reconoce una alerta.
- Tolerancia a un retraso de decenas de segundos en la alerta en la nube, dado que el plan gratuito puede dormir el servicio. La alarma local no depende de esto.
