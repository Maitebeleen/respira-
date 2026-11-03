# Cómo modificar el proyecto

Esta guía responde preguntas del tipo "quiero cambiar X, ¿dónde lo toco?". Para cada cambio indica el archivo, qué hacer y cómo comprobar que quedó bien.

Regla general antes de cambiar algo: **primero corre las pruebas, después cambia, después vuelve a correr las pruebas.** Si las pruebas no pasan, no subas el cambio.

## Mapa del código

| Carpeta o archivo | Qué contiene |
|---|---|
| `db/schema.sql` | Tablas, vista y revisión de silencio. Se aplica en Supabase. |
| `ingesta/app/main.py` | Las rutas de la API y el formato que se acepta. |
| `ingesta/app/ingesta.py` | Qué pasa con cada lote: token, sesiones, guardado y alertas. |
| `ingesta/app/reglas.py` | Umbrales y reglas de alerta. |
| `ingesta/app/notificar.py` | Envío de avisos a Telegram. |
| `ingesta/scripts/registrar.py` | Alta de máscaras y brigadistas. |
| `ingesta/tests/` | Pruebas. `test_reglas.py` no necesita base; `test_api.py` sí. |
| `simulador/simular.py` | Genera lecturas falsas para probar. |
| `ingesta/Dockerfile` | Cómo se empaqueta el servicio para Render. |
| `docs/` | Esta guía y el diseño original. |

## Cambiar un umbral de alerta

Ejemplo: bajar el aviso de CO de 35 a 30 ppm.

1. Abre `ingesta/app/reglas.py`.
2. Busca la línea de `CO_ALTO`:

    Regla("CO_ALTO", "co_ppm", "alto", (("CRITICA", 200.0), ("AVISO", 35.0))),

3. Cambia `35.0` por `30.0`.
4. Si tu cambio implica que el margen de rearme también cambie, revisa la función `fuera_de_margen`. Hoy rearma cuando el valor baja a menos del 90 % del aviso.
5. Ejecuta las pruebas de reglas:

    cd ingesta && .venv/bin/python -m pytest -q tests/test_reglas.py

6. Si las pruebas de reglas dicen que un caso esperado ya no se cumple, revisa si la prueba describe el comportamiento que quieres. A veces hay que actualizar la prueba también.
7. Sube el cambio a `main`. Render redespliega solo (ver "Publicar un cambio" más abajo).

**Importante:** la tabla `umbrales` de la base existe, pero el código no la lee todavía. Cambiar un valor en esa tabla **no cambia** las alertas. Mientras no se conecte, el lugar correcto es `reglas.py`.

## Agregar una regla nueva

Ejemplo: alertar si la temperatura de la máscara supera 45 °C.

1. Agrega la columna en `db/schema.sql` en la tabla `lecturas`, y el tipo de alerta en la lista de `alertas.tipo`.
2. Agrega el campo a `Lectura` en `ingesta/app/main.py`.
3. Agrega el campo al `insert` de `ingesta/app/ingesta.py`, tanto en las columnas como en la lista de valores.
4. Agrega la regla en `ingesta/app/reglas.py`:

    Regla("TEMP_ALTA", "temp_c", "alto", (("AVISO", 45.0),)),

5. Agrega las pruebas.
6. Aplica el cambio de esquema en Supabase. Las sentencias `alter table` nuevas se ejecutan en el SQL Editor. No vuelvas a correr `schema.sql` completo sobre una base con datos: borra nada, pero el archivo no está pensado para migraciones.

**Regla de oro:** cada campo nuevo debe existir en cuatro lugares: el esquema, el modelo de la API, el `insert` y las pruebas.

## Agregar una máscara o un brigadista

Desde la carpeta `ingesta/`, con el archivo `.env` cargado:

    .venv/bin/python scripts/registrar.py dispositivo RESP-0002 --version 0.1.0
    .venv/bin/python scripts/registrar.py brigadista B-018

- Cada máscara tiene su propio token. El token se muestra solo una vez.
- Los códigos de brigadista son seudónimos. Nunca pongas nombre ni RUT. La relación seudónimo y persona va en un registro aparte, fuera de la base.
- Para desactivar un brigadista sin borrarlo, en el SQL Editor: `update brigadistas set activo = false where seudonimo = 'B-017';`.

## Cambiar el tiempo de silencio

Hoy son 60 segundos. Para cambiarlo, edita `revisar_silencio()` en `db/schema.sql` (la frase `interval '60 seconds'` aparece dos veces) y vuelve a crear la función en el SQL Editor. La frecuencia de revisión es un minuto, y se cambia en la última parte del archivo.

## Cambiar la frecuencia de envío de la máscara

Eso lo decide el firmware del ESP32, no este proyecto. Lo que sí debes saber:
- Lotes de hasta 1000 lecturas por petición (límite en `Lote`).
- Cada lectura necesita `seq` único dentro de su `boot_id`.

## Activar avisos por Telegram

1. Crea un bot con `@BotFather` y guarda su token.
2. Obtén el identificador del chat (ver [04-replicar.md](04-replicar.md) o la guía de cuentas).
3. En Render, **Environment**, agrega `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
4. Render reinicia el servicio. Las alertas nuevas llegan al chat.

Si el envío falla, el servicio **no** deja de guardar datos: el error queda en los registros de Render.

## Conectar un dashboard

Hay dos formas.

- **Consumir la API:** el dashboard pide `GET /v1/estado` cada pocos segundos. Es lo más simple y no necesita tocar la base.
- **Leer la base directamente desde el navegador:** hoy no es posible. Las tablas tienen Row Level Security activado sin políticas, así que la clave pública (anon) no ve nada. Si quieres que un dashboard lea directo de Supabase, hay que escribir políticas de lectura específicas para una vista segura. No abras políticas amplias sobre `lecturas`, porque expondrían datos de salud.

## Publicar un cambio

1. Corre las pruebas (ver abajo).
2. Haz commit y push a `main`:

    git add -A
    git commit -m "Descripción corta del cambio"
    git push

3. Render detecta el cambio y redespliega solo. Revisa en su panel que el deploy quede en "Live".
4. Abre `/health` y prueba con el simulador.

**No subas cambios que rompan las pruebas.** Render despliega lo que esté en `main`.

## Correr las pruebas

    cd ingesta
    python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/respira .venv/bin/python -m pytest -q

Para correr solo las reglas (sin base de datos):

    .venv/bin/python -m pytest -q tests/test_reglas.py

Las pruebas de la API necesitan una base PostgreSQL desechable. Ver [04-replicar.md](04-replicar.md), parte F.

## Qué NO conviene cambiar sin pensarlo

- **El formato del contrato** (`POST /v1/lecturas`). El firmware del ESP32 depende de él. Si cambias un nombre de campo, hay que cambiar el firmware también.
- **La clave única de lecturas** `(dispositivo, boot_id, seq)`. Si la cambias, los reenvíos empiezan a duplicar datos.
- **El hash del token.** Si cambias el método, los tokens existentes dejan de funcionar.
- **El nivel de alarma local.** Esa decisión es de seguridad y pertenece al equipo de hardware, no a este servicio.
