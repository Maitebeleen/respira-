# Respira +: guía para entender y seguir el proyecto

Esta carpeta explica qué hay construido, para qué sirve cada pieza, por qué elegimos cada servicio y qué hay que hacer para replicarlo o cambiarlo. Está escrita para personas que no son programadoras.

## Qué es Respira +

Es una máscara para brigadistas forestales que mide el monóxido de carbono (CO) que respiran mientras combaten un incendio. Cuando el nivel sube, avisa al propio brigadista con una alarma en la máscara. Además, envía esa medición a una base de datos para que la central pueda ver qué le está pasando a cada brigadista y tomar decisiones.

Esta carpeta documenta solo la parte de datos: cómo la máscara envía información, dónde se guarda y cómo se consulta. La alarma local de la máscara es parte del diseño del equipo de hardware y no está aquí.

## Estado actual (3 de noviembre de 2026)

| Pieza | Estado |
|---|---|
| Base de datos en la nube (Supabase) | Creada y con el esquema aplicado |
| Servicio que recibe datos (Render) | Desplegado y respondiendo |
| Código en GitHub | Subido al repositorio de Maite |
| Prueba de punta a punta | Hecha con datos simulados |
| Máscara real (ESP32) | Pendiente |
| Dashboard web | Pendiente |
| Avisos por Telegram | Pendiente, opcional |
| Calibración del sensor MQ-7 | Pendiente |

## Mapa de esta carpeta

1. [01-servicios.md](01-servicios.md): qué es cada servicio externo (Supabase, Render, GitHub, Docker, PostgreSQL) y por qué lo elegimos.
2. [02-arquitectura.md](02-arquitectura.md): cómo viaja un dato desde la máscara hasta la base, con diagramas.
3. [03-lo-que-hicimos.md](03-lo-que-hicimos.md): el recorrido paso a paso y la razón de cada decisión.
4. [04-replicar.md](04-replicar.md): cómo crear todo desde cero con tus propias cuentas.
5. [05-modificar.md](05-modificar.md): cómo cambiar umbrales, agregar campos, máscaras o brigadistas, y dónde tocar el código.
6. [06-operacion.md](06-operacion.md): cómo revisar que todo funciona, qué hacer cuando falla y qué límites tienen los planes gratuitos.
7. [07-glosario.md](07-glosario.md): palabras técnicas explicadas en simple.

## Antes de empezar, cuatro cosas importantes

- **Las claves nunca van al repositorio.** Viven en archivos locales o en el panel de cada servicio. Si alguna clave se publica por error, hay que revocarla y crear otra.
- **Los datos de prueba no son reales.** Todo lo que está en la base hoy fue generado por un simulador.
- **Esto es un prototipo.** No se usa todavía para proteger personas. Antes de eso hay que validar el sensor, los umbrales y los procedimientos con prevención de riesgos.
- **Los datos de salud son sensibles.** La base guarda solo un seudónimo del brigadista, nunca el nombre ni el RUT. La relación entre seudónimo y persona debe llevarse fuera de la base, con acceso restringido.
