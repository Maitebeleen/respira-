# Respira +: cuentas y despliegue del MVP

Esta guía es para quien crea las cuentas del proyecto. Todas son gratuitas en su plan básico.

Importante: las cuentas deben crearse con el correo y la identidad de la persona responsable del proyecto. No comparta contraseñas por chat. Las claves se guardan en el panel de cada servicio o en el archivo `ingesta/.env` (que nunca se sube a GitHub).

## Qué cuentas se necesitan

| Servicio | Para qué sirve | Plan gratuito |
|---|---|---|
| Supabase | Base de datos PostgreSQL donde llegan las lecturas | Sí. Pausa el proyecto tras una semana sin actividad |
| GitHub | Repositorio del código del servicio de ingesta | Sí |
| Render | Aloja el servicio que recibe lecturas desde la máscara | Sí. Se duerme tras 15 minutos sin tráfico y despierta en 30 a 60 segundos |
| Telegram | Recibe las alertas en el celular de la central | Sí. Opcional: se puede activar después |

Más adelante (dashboard) podría usarse Grafana Cloud, también gratuito. No es necesario ahora.

## Paso 1. Supabase (base de datos)

1. Entre a https://supabase.com y cree una cuenta (puede usar GitHub o correo).
2. Pulse "New project". Nombre: `respira-plus`. Región: South America (São Paulo), para menor latencia desde Chile. Defina una contraseña de base de datos fuerte y guárdela en un gestor de contraseñas.
3. Espere a que el proyecto termine de crearse (uno o dos minutos).
4. Abra "SQL Editor", pegue el contenido completo del archivo `db/schema.sql` y ejecútelo. Debe terminar sin errores.
5. Revise la extensión de revisión de silencio: vaya a "Database", luego "Extensions", y confirme que `pg_cron` está habilitada. Si no lo está, habilítela y vuelva a ejecutar la última parte del archivo `schema.sql`.
6. Para obtener la cadena de conexión: "Project Settings", luego "Database", luego "Connection string", opción "Session pooler" o "Direct connection". Copie la cadena y reemplace `[YOUR-PASSWORD]` por la contraseña del paso 2.

La cadena tiene esta forma: `postgresql://postgres.<proyecto>:<contraseña>@<host>:5432/postgres`. Esa es la variable `DATABASE_URL`.

## Paso 2. GitHub (repositorio)

1. Entre a https://github.com y cree una cuenta.
2. Cree un repositorio privado llamado `respira-plus`. No lo inicialice con archivos.
3. Avise cuando esté listo. El código se sube desde este equipo al repositorio.

## Paso 3. Render (servicio de ingesta)

1. Entre a https://render.com y cree una cuenta con GitHub.
2. Pulse "New" y luego "Web Service". Conecte el repositorio `respira-plus`.
3. Configure:
   - Root Directory: `ingesta`
   - Runtime: Docker (usa el archivo `ingesta/Dockerfile`)
   - Plan: Free
4. En "Environment", agregue estas variables:
   - `DATABASE_URL`: la cadena del paso 1.
   - `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`: del paso 4 (opcional al principio; sin ellas las alertas solo quedan en el registro).
5. Pulse "Create Web Service". Al terminar, Render entrega una dirección del tipo `https://respira-plus-xxxx.onrender.com`. Pruebe que responde en `/health`.

## Paso 4. Telegram (alertas, opcional)

Este paso no es necesario para que los datos se guarden. Sin estas claves, las alertas quedan registradas en la base y en el log del servicio. Se puede omitir por ahora.

1. En Telegram, busque el usuario `@BotFather` y envíe `/newbot`.
2. Ponga un nombre y un usuario que termine en `bot`. BotFather entrega un token. Ese es `TELEGRAM_BOT_TOKEN`.
3. Abra el bot que creó y envíe un mensaje cualquiera.
4. Para obtener el identificador del chat, abra en el navegador `https://api.telegram.org/bot<TOKEN>/getUpdates` y copie el valor de `"chat":{"id": ...}`. Ese es `TELEGRAM_CHAT_ID`. Para un grupo de la central, agregue el bot al grupo, envíe un mensaje y repita el paso.

## Qué se necesita de vuelta

Para dejar todo funcionando, solo se necesitan estos datos, y es mejor cargarlos directamente en Render (paso 3) que enviarlos por chat:

1. La cadena `DATABASE_URL` (si prefiere enviarla, use un canal privado y cambie la contraseña después).
2. `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, solo si deciden activar las alertas por Telegram.
3. La dirección pública de Render.

## Registrar la primera máscara y un brigadista

Con la cadena `DATABASE_URL` en el archivo `ingesta/.env`, ejecute desde la carpeta `ingesta`:

    .venv/bin/python scripts/registrar.py dispositivo RESP-0001 --version 0.1.0
    .venv/bin/python scripts/registrar.py brigadista B-017

El token de la máscara se muestra una sola vez. Guárdelo para el firmware del ESP32.

## Probar sin hardware

Desde la carpeta `simulador`:

    python simular.py --url https://respira-plus-xxxx.onrender.com --token <TOKEN> --brigadista B-017 --pico-co 60

Debe responder 200 en cada lote. Si el pico supera 35 ppm, llega una alerta a Telegram.

## Advertencias del prototipo

- Este sistema no reemplaza la alarma local de la máscara ni es un equipo de protección certificado.
- El sensor MQ-7 necesita calibración en terreno antes de que sus lecturas sean confiables. Los umbrales de alerta son propuestas que deben validarse con prevención de riesgos y con la normativa chilena vigente.
- La base solo guarda seudónimos de brigadistas. La relación entre seudónimo y persona debe llevarse fuera de la base, con acceso restringido. Los datos de salud son sensibles según la Ley 21.719.
- El plan gratuito de Render puede tardar en responder cuando el servicio estuvo dormido. La alarma local no depende de esto.
