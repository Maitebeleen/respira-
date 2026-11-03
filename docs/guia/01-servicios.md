# Los servicios, explicados en simple

El proyecto usa cinco herramientas. Cuatro son servicios en internet (cuentas que alguien crea) y una es un programa que corre dentro de la máscara o en la computadora.

## 1. GitHub: donde vive el código

**Qué es:** un sitio donde se guardan proyectos de código y se lleva su historia. Cada cambio queda registrado con fecha, autor y descripción.

**Qué hace en Respira +:**
- Guarda todos los archivos del proyecto en el repositorio `Maitebeleen/respira-`.
- Es la fuente de verdad: lo que está ahí es lo que se despliega.
- Render lee el repositorio para construir el servicio.

**Por qué lo elegimos:** es gratuito, Render lo soporta directamente y el repositorio puede ser privado.

**Importante:** el repositorio no contiene claves. El archivo `.env` está excluido con `.gitignore`.

## 2. Supabase: la base de datos

**Qué es:** un servicio que te da una base de datos PostgreSQL lista para usar, con panel web, copias de seguridad y acceso por internet.

**Qué es PostgreSQL:** es un programa que guarda información en tablas, parecidas a hojas de cálculo que se relacionan entre sí. Es uno de los más usados en el mundo y es gratuito.

**Qué hace en Respira +:**
- Guarda los brigadistas (con seudónimo), las máscaras, las sesiones de uso, cada lectura de CO y las alertas.
- Ejecuta cada minuto una revisión que detecta si una máscara dejó de enviar datos (`pg_cron`).

**Por qué lo elegimos:** el plan gratuito incluye una base PostgreSQL completa. Elegimos la región São Paulo para tener menos demora desde Chile.

**Límite del plan gratuito:** si el proyecto no tiene actividad durante una semana, Supabase lo pausa. Se reactiva desde el panel.

## 3. Render: el servicio que recibe los datos

**Qué es:** un servicio donde se publican programas que deben estar encendidos todo el tiempo y responder por internet, como una página web o una API.

**Qué es una API:** un programa que recibe pedidos de otros programas y responde con datos. Por ejemplo, la máscara envía "estas son mis últimas lecturas" y la API responde "guardadas".

**Qué hace en Respira +:**
- Corre el servicio `respira-ingesta`, escrito en Python con la librería FastAPI.
- Recibe los lotes de lecturas de la máscara, revisa el token de la máscara, guarda sin duplicar y genera alertas.
- Responde en `https://respira-ingesta.onrender.com`.

**Por qué lo elegimos:** tiene plan gratuito para servicios con Docker, se conecta a GitHub y redespliega solo cuando hay cambios en `main`.

**Límite del plan gratuito:** si no recibe tráfico durante unos 15 minutos, el servicio se duerme. La siguiente petición tarda entre 30 y 60 segundos en responder. La máscara debe reintentar en ese caso, y el buffer del dispositivo evita perder lecturas.

## 4. Docker: la caja donde corre el programa

**Qué es:** una forma de empaquetar un programa junto con todo lo que necesita para correr (versión de Python, librerías, archivos). Esa "caja" se llama contenedor.

**Por qué importa:** asegura que el programa funcione igual en tu computadora, en Render o en la de otra persona.

**Dónde está en el proyecto:** el archivo `ingesta/Dockerfile` contiene las instrucciones para armar la caja. Describe: usar Python 3.12, instalar las librerías de `requirements.txt`, copiar la carpeta `app` y arrancar el servidor.

## 5. ESP32: el microcontrolador de la máscara (todavía no conectado)

**Qué es:** una placa pequeña, del tamaño de una moneda grande, con Wi-Fi y pines para conectar sensores. Es como una computadora muy simple que lee sensores y hace decisiones.

**Qué hará en Respira +:**
- Leer el sensor de CO (MQ-7) y otros sensores.
- Activar la alarma local (buzzer y luz) si el nivel es peligroso, sin depender de internet.
- Guardar las lecturas en memoria cuando no hay señal y enviarlas en lotes cuando vuelve la conexión.

**Estado:** el firmware no está escrito. Lo que sí existe es el contrato, es decir, el formato exacto de los mensajes que enviará. Está descrito en [02-arquitectura.md](02-arquitectura.md).

## 6. Telegram: avisos a celulares (opcional, desactivado)

**Qué es:** una aplicación de mensajería que permite crear bots, programas que escriben mensajes.

**Qué haría en Respira +:** enviar una alerta al celular de la central cuando hay CO alto o una máscara sin señal.

**Estado:** el código está preparado pero desactivado. Si no se configuran `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, las alertas solo quedan en la base y en el registro del servicio. Se activa cuando el equipo lo decida.

## Cómo se conectan entre sí

Los servicios no se comunican entre sí directamente, salvo Render con GitHub y Render con Supabase:

- GitHub entrega el código a Render.
- Render lee y escribe en Supabase.
- La máscara (ESP32) envía datos a Render.
- Quien consulte el estado (hoy, un navegador o `curl`; mañana, el dashboard) lee desde Render.

En [02-arquitectura.md](02-arquitectura.md) está el diagrama completo.
