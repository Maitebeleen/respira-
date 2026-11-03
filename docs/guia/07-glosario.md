# Glosario en palabras simples

**API:** un programa que recibe pedidos de otros programas y responde con datos. Por ejemplo, "dame el estado de las máscaras".

**Base de datos:** el lugar donde se guarda la información de forma ordenada, en tablas.

**Brigadista (seudónimo):** el código con que se identifica a una persona en la base, por ejemplo `B-017`. El nombre real no aparece en la base.

**Buffer:** memoria temporal donde la máscara guarda lecturas mientras no tiene señal. Cuando vuelve la conexión, envía lo guardado.

**CO (monóxido de carbono):** gas sin olor ni color que produce el humo de los incendios. Es peligroso porque la sangre lo absorbe en lugar del oxígeno.

**ppm (partes por millón):** forma de medir concentración. 35 ppm significa 35 partes de gas por cada millón de partes de aire.

**Contenedor:** ver Docker.

**Deploy (despliegue):** poner una versión del código en funcionamiento en un servicio de internet.

**Dockerfile:** archivo con las instrucciones para armar un contenedor.

**ESP32:** microcontrolador, una placa pequeña con Wi-Fi que lee sensores y ejecuta un programa.

**Esquema:** la descripción de las tablas de la base: qué columnas tienen y qué tipo de dato guarda cada una.

**Firmware:** el programa que vive dentro del ESP32. No está escrito todavía.

**Hash:** una huella de un texto, calculada de forma que no se puede volver al texto original. Se guarda el hash del token para poder verificarlo sin guardar el token.

**Histéresis:** regla que evita que una alerta se active y desactive sin parar cuando el valor oscila cerca del umbral. Aquí: la alerta se rearma solo cuando el valor baja del 90 % del umbral.

**Idempotencia:** propiedad de hacer algo dos veces y que el resultado sea el mismo que hacerlo una vez. Aquí, reenviar un lote no duplica lecturas.

**Lote:** un paquete de varias lecturas enviado en una sola petición.

**Lectura:** una medición con su hora: CO, oxígeno, presión, batería, etc.

**MQ-7:** sensor barato de monóxido de carbono. Sirve para prototipos, pero necesita calibración para dar valores confiables.

**pg_cron:** programa dentro de Supabase que ejecuta funciones de la base en horarios fijos, por ejemplo cada minuto.

**PostgreSQL:** programa de base de datos muy usado y gratuito. Es el motor que hay detrás de Supabase.

**Pooler:** intermediario entre el servicio y la base que administra las conexiones. Supabase lo ofrece con dos modos: sesión (puerto 5432) y transacción (puerto 6543).

**Repositorio:** carpeta de proyecto guardada en GitHub con su historia de cambios.

**RLS (Row Level Security):** función de la base que decide qué filas puede ver o cambiar cada usuario. Aquí está activada sin reglas, así que solo el servicio de Render puede tocar los datos.

**Rearmar una alerta:** volver a dejar la alerta lista para que se active de nuevo, después de que el valor volvió a la normalidad.

**Seq (número de orden):** número que la máscara pone a cada lectura dentro de un mismo encendido. Sirve para detectar repetidos y huecos.

**Servicio:** un programa que corre en internet de forma continua, como el de Render en este proyecto.

**Sesión (de uso):** periodo en que una máscara está asignada a un brigadista. Empieza cuando llega una lectura con ese brigadista y termina tras 15 minutos sin lecturas o cuando cambia de brigadista.

**Token:** una clave secreta larga que identifica a una máscara. Va en cada envío para demostrar quién es.

**Umbral:** valor a partir del cual se genera una alerta. Por ejemplo, 35 ppm de CO.

**UUID:** identificador largo que parece aleatorio, por ejemplo `687f1b8b-89d7-45c1-bc8d-ab331913a2bd`. Se usa para que los identificadores no se repitan.

**Vista:** una consulta guardada en la base que se comporta como una tabla de solo lectura. `ultimo_estado` es una vista.
