# Cómo replicar todo desde cero

Esta guía sirve si quieres levantar el mismo sistema con tus propias cuentas, por ejemplo para otra máscara, otro equipo o una prueba separada de la que ya existe. Tarda unos 45 minutos la primera vez.

Necesitas:
- Una cuenta de GitHub.
- Una cuenta de Supabase.
- Una cuenta de Render.
- Opcional: una cuenta de Telegram, si quieres avisos.
- En tu computadora: Git, Python 3.12 o superior y Docker (solo si quieres probar en local).

## Parte A: copiar el código

1. Entra al repositorio y haz **Fork** (copia en tu cuenta) o descárgalo con `git clone`.
2. Si lo descargas, cambia el remoto a tu propio repositorio:

    git remote set-url origin https://github.com/<tu-usuario>/<tu-repo>.git
    git push -u origin main

3. Verifica que en la raíz están `db/`, `ingesta/`, `simulador/` y `docs/`.

## Parte B: crear la base en Supabase

1. Entra a https://supabase.com y crea una cuenta.
2. Pulsa **New project**:
   - Nombre: el que quieras, por ejemplo `respira-plus`.
   - Región: **South America (São Paulo)**.
   - Contraseña de base de datos: genera una larga y guárdala en un gestor de contraseñas. Esta contraseña no se puede recuperar después, solo cambiar.
3. Espera a que el estado sea "Healthy", unos dos minutos.
4. Abre **SQL Editor**, pega todo el contenido de `db/schema.sql` y pulsa **Run**.
5. Revisa que no haya errores. Si aparece un aviso sobre `pg_cron`, ve a **Database > Extensions**, activa `pg_cron` y vuelve a ejecutar el archivo.
6. Confirma en **Table Editor** que aparecen las tablas: `brigadistas`, `dispositivos`, `sesiones`, `lecturas`, `alertas`, `estado_alerta`, `umbrales`.
7. Para obtener la cadena de conexión: **Connect**, luego **Session pooler**. La forma es:

    postgresql://postgres.<referencia-del-proyecto>:<contraseña>@<host-del-pooler>:5432/postgres

   Reemplaza `<contraseña>` por la contraseña del paso 2. El host y la referencia aparecen en esa misma pantalla.

**Por qué el puerto 5432 y no el 6543:** el puerto 6543 es el modo transacción del pooler. El driver de Python usa consultas preparadas, que ese modo no admite. Con 5432 (modo sesión) funciona sin problemas.

## Parte C: publicar el servicio en Render

1. Entra a https://render.com y crea una cuenta con GitHub.
2. En **Account Settings > Git Providers**, conecta GitHub y autoriza **solo el repositorio** que vas a usar.
3. Pulsa **New > Web Service** y elige el repositorio.
4. Completa:

| Campo | Valor |
|---|---|
| Name | `respira-ingesta` (o el que quieras; debe ser único en Render) |
| Branch | `main` |
| Region | Oregon (la más cercana disponible en el plan gratuito) |
| Root Directory | **vacío** |
| Language | Docker |
| Dockerfile Path | `./ingesta/Dockerfile` |
| Docker Build Context Directory | `./ingesta` |
| Instance Type | Free |
| Auto-Deploy | Yes |
| Health Check Path | `/health` |

5. En **Environment Variables** agrega:
   - `DATABASE_URL` = la cadena del paso B.7.
   - Opcional: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, si activas Telegram.
6. Pulsa **Create Web Service** y espera a que el deploy esté en "Live".
7. Abre `https://<tu-servicio>.onrender.com/health`. Debe responder `{"ok":true}`.

Si el build falla con un error del tipo `"/app": not found`, revisa que el Dockerfile path y el build context estén como en la tabla. Ese fue el error que nosotros tuvimos.

## Parte D: registrar una máscara y un brigadista

Desde tu computadora, dentro de la carpeta `ingesta/` (antes instala dependencias):

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Crea un archivo `.env` (no lo subas a GitHub) con:

    DATABASE_URL=postgresql://postgres.<referencia>:<contraseña>@<host>:5432/postgres

Luego ejecuta:

    set -a && . ./.env && set +a
    .venv/bin/python scripts/registrar.py dispositivo RESP-0001 --version 0.1.0
    .venv/bin/python scripts/registrar.py brigadista B-017

El primer comando muestra un token. **Cópialo y guárdalo** en un lugar seguro: no se vuelve a mostrar. Ese token es el que irá en el firmware de la máscara.

## Parte E: probar con el simulador

Desde la carpeta `simulador/`:

    python3 simular.py --url https://<tu-servicio>.onrender.com --token <token> --brigadista B-017 --pico-co 60

Debe imprimir `200` en cada lote. Luego puedes ver el estado:

    curl https://<tu-servicio>.onrender.com/v1/estado

Si el pico de CO supera 35 ppm, la base guarda una alerta `CO_ALTO` de AVISO. Puedes verla en el **Table Editor** de Supabase, tabla `alertas`.

## Parte F: probar en tu computadora antes de tocar la nube

Si quieres experimentar sin afectar nada:

    docker run -d --name respira-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=respira -p 5433:5432 postgres:16-alpine
    psql "postgresql://postgres:test@localhost:5433/respira" -f db/schema.sql
    cd ingesta && TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/respira .venv/bin/python -m pytest -q

Las pruebas borran el esquema de la base que se les indique. Usa siempre una base desechable.

## Qué guardar al final

- La cadena `DATABASE_URL` (solo en Render y en `.env` local).
- Los tokens de cada máscara (solo en el firmware y en un lugar seguro).
- La clave de API de Render, si la creaste.
- El token de Supabase, si lo creaste.

Nada de esto va al repositorio. Si alguna clave se publica, sigue el procedimiento de [06-operacion.md](06-operacion.md).
