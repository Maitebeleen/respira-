# Operación: revisar, arreglar y cuidar el sistema

Esta guía es para el día a día: cómo saber si todo funciona, qué hacer cuando algo falla y qué cuidar.

## Chequeo rápido (30 segundos)

1. ¿Responde el servicio?

    curl https://respira-ingesta.onrender.com/health

   Respuesta esperada: `{"ok":true}`.

2. ¿Llegan datos recientes?

    curl https://respira-ingesta.onrender.com/v1/estado

   Mira el campo `ts_recepcion`. Si la fecha es de hace horas, no hay máscara enviando.

3. ¿Hay alertas nuevas? En el panel de Supabase, **Table Editor > alertas**, ordena por `creada_en`.

## Dónde mirar cuando algo falla

| Síntoma | Dónde mirar | Causa típica |
|---|---|---|
| `/health` no responde | Render > servicio > **Logs** | El servicio se durmió (tarda 30 a 60 s en despertar) o hubo error al arrancar |
| El deploy quedó en `build_failed` | Render > **Events** o **Logs** | Cambio que rompe el Dockerfile o las dependencias |
| La máscara recibe `401` | Respuesta de la API | Token incorrecto o máscara no registrada |
| La máscara recibe `422` | Respuesta de la API | Brigadista no registrado o no activo |
| La máscara recibe `500` | Render > **Logs** | Error del servicio o de la base. Revisa el mensaje |
| No llegan datos aunque la máscara está encendida | Supabase > **Project Settings > General** | El proyecto está pausado |
| Hay lecturas pero no alertas | `alertas` en Supabase | Los umbrales no se cruzaron, o la alerta ya estaba activa (no se repite antes de 60 s) |

### Qué hacer cuando el servicio está dormido

Render duerme el plan gratuito tras 15 minutos sin tráfico. La primera petición tarda más. La máscara debe reintentar. Si quieres evitarlo, un chequeo periódico a `/health` lo mantiene despierto, por ejemplo con un servicio gratuito de monitoreo como UptimeRobot. Eso consume horas del plan gratuito de Render, así que hay que vigilarlo.

### Qué hacer cuando Supabase está pausado

Supabase pausa el proyecto gratuito tras una semana sin actividad. Para reactivarlo: panel de Supabase, abre el proyecto y pulsa **Restore**. Tarda unos minutos.

Para evitar la pausa, el envío de datos de la máscara ya es actividad. Pero si la máscara no se usa durante semanas, el proyecto se pausará igual.

## Límites del plan gratuito (verifica en cada plataforma, cambian con el tiempo)

| Servicio | Límite importante | Qué pasa si se supera |
|---|---|---|
| Supabase | 500 MB de base de datos, 2 proyectos activos por cuenta | No se pueden guardar más datos hasta limpiar o cambiar de plan |
| Supabase | Pausa tras una semana sin actividad | Hay que reactivarlo a mano |
| Render | 750 horas de servicio al mes, un servicio gratis activo | El servicio se detiene el resto del mes |
| Render | Duerme tras 15 min sin tráfico | Primera petición lenta |
| GitHub | Repositorios privados ilimitados | Sin límite práctico para este proyecto |

Las cifras cambian. Antes de una demo, revisa las páginas de precios de cada servicio.

## Cuánto ocupan los datos

Cada lectura ocupa unos cientos de bytes. Con una máscara enviando una lectura por segundo durante 8 horas, son unas 28.800 lecturas por día, unos pocos megabytes. Con varias máscaras, el límite de 500 MB puede llegar en semanas. Por eso conviene:
- Borrar los datos de prueba antes de empezar en serio.
- Revisar el tamaño en Supabase: **Project Settings > Database > Disk usage**.
- Pensar una política de retención antes de llegar al límite (por ejemplo, conservar 6 meses).

## Limpiar datos de prueba

Estos datos son simulados: la máscara `RESP-0001`, el brigadista `B-017` y todas sus lecturas y alertas. Para borrarlos, desde el SQL Editor de Supabase, **después de confirmar con el equipo**:

    delete from alertas;
    delete from estado_alerta;
    delete from lecturas;
    delete from sesiones;
    delete from brigadistas where seudonimo = 'B-017';
    delete from dispositivos where codigo = 'RESP-0001';

**No lo ejecutes sin confirmar.** Borra todo lo que esté en esas tablas, sin posibilidad de recuperarlo.

## Rotar claves

Cuando una clave se publica, se expone en un chat, se copia por error o cambia de responsable, hay que reemplazarla.

| Clave | Dónde se crea | Dónde se reemplaza | Efecto |
|---|---|---|---|
| Clave de Render | Render > Account Settings > API Keys | Revocar la vieja y actualizar `~/.config/respira/render.env` | Solo afecta a scripts que la usen |
| Token de Supabase (`sbp_`) | Supabase > Account > Access Tokens | Revocar y actualizar `~/.config/respira/supabase.env` | Solo afecta a scripts que la usen |
| Contraseña de la base | Supabase > Project Settings > Database > Reset password | En Render (`DATABASE_URL`) y en `.env` local | **Corta el servicio hasta actualizar Render** |
| Token de una máscara | No se rota en la base. Registrar una máscara nueva o cambiar el hash | Firmware del ESP32 | Hay que volver a grabar la máscara |

Orden recomendado si sospechas que la contraseña de la base se filtró:
1. Cambia la contraseña en Supabase.
2. Actualiza `DATABASE_URL` en Render. Render reinicia el servicio.
3. Actualiza `.env` local.
4. Revisa que `/health` y el simulador sigan funcionando.

## Seguridad: qué ya está hecho y qué falta

Hecho:
- Row Level Security activado en todas las tablas, sin políticas. La clave pública no puede leer ni escribir datos.
- La función de revisión de silencio no se puede llamar desde la API pública.
- El token de cada máscara se guarda como hash.
- El servicio solo escribe datos; no hay forma de borrar desde la API.
- El repositorio no contiene claves.

Falta:
- **Rotar las claves pegadas en el chat del proyecto.** Esto es lo más urgente.
- Política de retención y respaldo. Supabase hace copias en planes de pago. En el plan gratuito no hay respaldo automático garantizado: exporta lo importante a mano.
- Autenticación para quien consulte `/v1/estado`. Hoy cualquiera con la dirección puede verlo. Antes de usar datos reales hay que cerrarlo, por ejemplo con una clave de lectura.
- Revisar la Ley 21.719 (datos personales y sensibles) con alguien del área legal antes de guardar datos reales de personas.
- Validar umbrales y sensor con prevención de riesgos.

## Quién hace qué

Definir esto antes de usar el sistema en terreno:
- **Quién recibe las alertas.** Hoy nadie, porque Telegram está apagado.
- **Quién tiene acceso a las claves.** Idealmente una sola persona, con copia en un gestor de contraseñas.
- **Quién revisa los datos y decide** cuando un brigadista debe retirarse.
- **Quién responde cuando el servicio cae.** Un número de contacto y un horario.
