# Lo que hicimos, paso a paso, y por qué

Esta es la historia del proyecto en orden, con la razón de cada decisión. Sirve para entender por qué las cosas están como están antes de cambiarlas.

## Fase 0: entender el problema

Lo que sabíamos por las láminas del proyecto:
- Los brigadistas forestales respiran monóxido de carbono durante los incendios, y hoy no existe nada que lo mida mientras trabajan.
- La máscara actual filtra partículas, pero no protege del CO. Además, el CO no se nota con los sentidos.
- La central de CONAF tiene información general, pero no sabe en tiempo real cuánto CO respira cada brigadista.

De ahí salieron dos objetivos: **proteger** al brigadista con una alarma local, e **informar** a la central con datos en tiempo real.

## Fase 1: diseño antes de construir

Antes de escribir código hicimos un diseño escrito: [docs/superpowers/specs/2026-11-03-respira-mvp-design.md](../superpowers/specs/2026-11-03-respira-mvp-design.md).

Lo que decidimos y por qué:

| Decisión | Por qué |
|---|---|
| Servicios gratuitos | El proyecto es un prototipo y no tiene presupuesto. |
| Base PostgreSQL | Es estándar, gratuita y sirve para datos con fecha, como las mediciones. |
| Envío por HTTPS en lotes, no en tiempo real | Es más simple de depurar. Un lote tolera cortes de Wi-Fi mejor que una conexión continua. |
| Servicio intermedio (Render) entre la máscara y la base | La máscara no debe conocer la contraseña de la base. Si alguien roba una máscara, solo tiene un token que se puede revocar. |
| Solo seudónimo del brigadista | Los datos de salud son sensibles y la ley chilena los protege (Ley 21.719). |
| La alarma es local | Si la alarma dependiera de internet, un corte de señal dejaría al brigadista sin protección. |

Después de escribir el diseño, lo revisó un agente independiente que hizo de constructor. Nos hizo cinco preguntas. Tres las respondimos como decisiones técnicas que quedaron documentadas: cómo se abre una sesión, cómo se detecta el silencio y cómo se evitan duplicados al reiniciar la máscara. Dos quedaron pendientes para ustedes: quién recibe los avisos y cuánto retraso se acepta en la nube.

## Fase 2: la base de datos

Escribimos el esquema en `db/schema.sql`. Es un solo archivo que crea todas las tablas, la vista y la revisión de silencio.

Antes de tocar la nube, lo probamos en una base local, en Docker, en el puerto 5433. Así un error no afecta a nadie.

Puntos que vale la pena entender:
- **Idempotencia:** cada lectura tiene una clave formada por máscara, encendido y número de orden. Si la máscara reenvía el mismo lote, la base lo ignora. Así se evitan duplicados sin complicar a la máscara.
- **Encendido (`boot_id`):** cuando la máscara se reinicia, el número de orden puede volver a cero. Por eso la clave incluye el número de encendido, para no descartar lecturas nuevas.
- **Vista `ultimo_estado`:** permite consultar rápido el estado actual de cada máscara sin recorrer toda la historia.

## Fase 3: el servicio de ingesta

Escribimos la API en Python con FastAPI, en la carpeta `ingesta/`. Las partes importantes:

- **`app/reglas.py`:** las reglas de alerta. Son funciones puras, es decir, no tocan la base, así que se pueden probar solas. Están probadas con 10 pruebas.
- **`app/ingesta.py`:** lo que pasa con cada lote. Verifica el token, resuelve el brigadista, gestiona la sesión, guarda sin duplicar y genera alertas.
- **`app/main.py`:** las rutas que responden por internet. `POST /v1/lecturas` recibe lotes, `GET /v1/estado` muestra el estado actual y `GET /health` dice si el servicio está vivo.
- **`app/notificar.py`:** envía alertas a Telegram si está configurado. Hoy está apagado.
- **`scripts/registrar.py`:** registra máscaras y brigadistas. Genera el token de la máscara y lo muestra una sola vez.

Además probamos todo con 19 pruebas automáticas contra una base PostgreSQL real. Todas pasaron.

**Por qué se guarda solo el hash del token:** si alguien consulta la base, no puede obtener los tokens de las máscaras. Solo se compara el hash con el token que llega.

## Fase 4: simulador

Como todavía no hay máscara real, escribimos `simulador/simular.py`. Genera lecturas con la misma forma que enviará el ESP32 y permite probar el sistema completo. Por ejemplo, simula un aumento de CO hasta 60 ppm y luego una bajada.

## Fase 5: publicar el servicio

1. **Código en GitHub:** subimos el proyecto al repositorio de Maite. Quedó privado, con un solo commit inicial.
2. **Render:** creamos un servicio web de tipo Docker, apuntando a `ingesta/Dockerfile`.
3. **El primer build falló.** La causa: el contexto de Docker estaba configurado en la raíz del repositorio, y el Dockerfile necesitaba estar dentro de `ingesta/`. Lo corregimos con la API de Render y el segundo build pasó.
4. **Supabase:** creamos el proyecto en São Paulo, aplicamos el esquema y comprobamos que las tablas y la revisión de silencio existen.
5. **Conexión:** cargamos `DATABASE_URL` en Render. Usamos el pooler en modo sesión (puerto 5432), porque el modo transacción (6543) no admite las consultas preparadas que usa el driver de Python.

## Fase 6: prueba de punta a punta

Registramos la máscara `RESP-0001` y el brigadista `B-017`. Luego enviamos 60 lecturas simuladas a la dirección pública de Render.

Resultado:
- Las 60 lecturas se aceptaron.
- `/v1/estado` mostró la última lectura con su brigadista asignado.
- Se generó una alerta `CO_ALTO` de AVISO al cruzar 35 ppm.

Lo que **no** probamos todavía: que la revisión de silencio genere alertas. Confirmamos que el trabajo de `pg_cron` existe, pero no esperamos a que se dispare con una máscara apagada.

## Fase 7: revisión de seguridad

Al revisar la guía, comprobamos algo que habíamos dejado sin resolver: Supabase expone automáticamente las tablas de `public` a su clave anónima, la que usa un navegador. Probamos con la clave del proyecto y **sí se podían leer las lecturas**.

Lo corregimos así:
1. Activamos Row Level Security en todas las tablas, sin políticas. Con eso, la clave anónima no ve ni escribe nada.
2. Quitamos permisos a los roles `anon` y `authenticated` sobre tablas, vistas y funciones.
3. Verificamos que la clave anónima ahora recibe 401, y que el servicio en Render sigue guardando y mostrando datos.

Por qué el servicio sigue funcionando: Render se conecta como `postgres`, el dueño de las tablas. Ese rol no pasa por las reglas de RLS. Por eso la seguridad está en no dar acceso a las claves públicas, no en el servicio.

Lo que todavía falta: la consulta de `/v1/estado` no tiene autenticación. Cualquiera con la dirección puede verla. Antes de usar datos reales hay que cerrarla.

## Errores que tuvimos y cómo los resolvimos

| Problema | Causa | Solución |
|---|---|---|
| Render no veía el repositorio | La cuenta de Render no tenía conectado GitHub | Conectar GitHub en Account Settings y autorizar solo ese repositorio |
| Build de Docker fallaba | Contexto de build en la raíz, no en `ingesta/` | Cambiar `dockerfilePath` y `dockerContext` |
| Health check no respondía al principio | El servicio tardaba en arrancar tras el primer build | Esperar a que el deploy quedara `live` |
| Error al serializar UUID en `/v1/estado` | JSON no sabe convertir UUID automáticamente | Convertir los valores antes de responder |

## Qué no hicimos a propósito

- **No conectamos Telegram.** Los datos no dependen de eso. Se puede activar después.
- **No hicimos el dashboard.** Por ahora se consulta `/v1/estado`. El dashboard se hace cuando haya datos reales.
- **No escribimos el firmware del ESP32.** Antes hay que decidir el sensor, la calibración y la forma de la alarma local.
- **No borramos los datos de prueba.** Se borran cuando el equipo lo confirme.
