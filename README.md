# Respira +

Prototipo de telemetría para la máscara de protección respiratoria de brigadistas.

**Empieza por [docs/guia/00-leeme-primero.md](docs/guia/00-leeme-primero.md).** Ahí está todo explicado en palabras simples, con diagramas.

- [Guía completa](docs/guia/00-leeme-primero.md): qué es cada servicio, cómo viaja un dato, qué hicimos y por qué, cómo replicar y cómo modificar.
- [Cuentas y despliegue](docs/cuentas_y_despliegue.md): pasos originales para crear las cuentas.

- `docs/guia/`: guía completa para entender y seguir el proyecto.
- `docs/superpowers/specs/`: documento de diseño del MVP.
- `docs/cuentas_y_despliegue.md`: cuentas que hay que crear y pasos para desplegar.
- `db/schema.sql`: esquema de PostgreSQL (Supabase). Incluye la revisión de silencio con pg_cron.
- `ingesta/`: API FastAPI que recibe lotes de lecturas, guarda sin duplicar y genera alertas.
  - `app/reglas.py`: umbrales y histéresis de alertas (funciones puras, sin base).
  - `scripts/registrar.py`: registra máscaras (genera token) y brigadistas (seudónimo).
  - `tests/`: pruebas de reglas y de la API contra PostgreSQL real.
- `simulador/simular.py`: envía lecturas simuladas con el contrato del ESP32.
- `simulador/chequeo.py`: prueba el servicio desplegado de punta a punta.
- `firmware/respira-esp32/`: programa de la máscara (ESP32 + MQ-7). Ver [docs/guia/08-esp32-mq7.md](docs/guia/08-esp32-mq7.md).

## Probar localmente

    docker run -d --name respira-pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=respira -p 5433:5432 postgres:16-alpine
    cd ingesta && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/respira .venv/bin/python -m pytest -q

`TEST_DATABASE_URL` debe apuntar a una base desechable: las pruebas borran el esquema.

## Estado

- Hecho: esquema, ingesta con idempotencia, sesiones, alertas con histéresis, registro de máscaras, simulador, pruebas.
- Pendiente: prueba del firmware con hardware real, dashboard web, umbrales en base de datos, calibración del MQ-7, autenticación de la consulta de estado y rotación de claves.
