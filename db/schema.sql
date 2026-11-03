-- Respira +: esquema de la base de datos (PostgreSQL, compatible con Supabase).
-- Ejecutar completo en el SQL Editor de Supabase o con psql. Es idempotente en lo básico.

create extension if not exists pgcrypto;

-- Brigadistas: solo seudónimo. Nunca nombre ni RUT en esta base.
create table if not exists brigadistas (
    id          uuid primary key default gen_random_uuid(),
    seudonimo   text not null unique,
    activo      boolean not null default true,
    creado_en   timestamptz not null default now()
);

-- Dispositivos (máscaras). El token en claro nunca se guarda; solo su hash sha256.
create table if not exists dispositivos (
    id                uuid primary key default gen_random_uuid(),
    codigo            text not null unique,
    token_hash        text not null,
    version_firmware  text,
    creado_en         timestamptz not null default now()
);

-- Sesiones: periodo en que una máscara está asignada a un brigadista.
create table if not exists sesiones (
    id             uuid primary key default gen_random_uuid(),
    dispositivo_id uuid not null references dispositivos(id),
    brigadista_id  uuid not null references brigadistas(id),
    inicio         timestamptz not null default now(),
    fin            timestamptz,
    incidente      text
);
-- Como máximo una sesión abierta por máscara.
create unique index if not exists sesion_abierta_unica
    on sesiones (dispositivo_id) where fin is null;

-- Lecturas: una fila por medición del ESP32.
-- La clave única (dispositivo, boot_id, seq) hace idempotente el reenvío de lotes.
create table if not exists lecturas (
    id               bigserial primary key,
    dispositivo_id   uuid not null references dispositivos(id),
    sesion_id        uuid references sesiones(id),
    boot_id          integer not null,
    seq              integer not null,
    ts_dispositivo   timestamptz,
    ts_recepcion     timestamptz not null default now(),
    co_ppm           numeric(8,2) not null check (co_ppm >= 0),
    o2_pct           numeric(5,2) check (o2_pct between 0 and 100),
    presion_bar      numeric(6,1) check (presion_bar >= 0),
    filtro_ok        boolean,
    bateria_pct      smallint check (bateria_pct between 0 and 100),
    alarma_local     boolean not null default false,
    lat              double precision,
    lon              double precision,
    unique (dispositivo_id, boot_id, seq)
);
create index if not exists lecturas_sesion_idx on lecturas (sesion_id, ts_recepcion);
create index if not exists lecturas_disp_idx on lecturas (dispositivo_id, ts_recepcion desc);

-- Umbrales configurables sin tocar código.
create table if not exists umbrales (
    tipo      text not null,
    nivel     text not null check (nivel in ('AVISO', 'CRITICA')),
    valor     numeric(8,2) not null,
    vigente   boolean not null default true,
    primary key (tipo, nivel)
);
insert into umbrales (tipo, nivel, valor) values
    ('CO_ALTO',      'AVISO',   35),
    ('CO_ALTO',      'CRITICA', 200),
    ('O2_BAJO',      'AVISO',   19.5),
    ('PRESION_BAJA', 'AVISO',   50),
    ('BATERIA_BAJA', 'AVISO',   20)
on conflict (tipo, nivel) do nothing;

-- Alertas generadas por el servicio de ingesta o por la revisión de silencio.
create table if not exists alertas (
    id              bigserial primary key,
    dispositivo_id  uuid not null references dispositivos(id),
    sesion_id       uuid references sesiones(id),
    tipo            text not null check (tipo in
                      ('CO_ALTO','O2_BAJO','PRESION_BAJA','BATERIA_BAJA','SIN_SENAL','SIN_ASIGNAR')),
    nivel           text not null check (nivel in ('AVISO', 'CRITICA')),
    valor           numeric,
    umbral          numeric,
    creada_en       timestamptz not null default now(),
    reconocida_en   timestamptz,
    reconocida_por  text
);
create index if not exists alertas_abiertas_idx on alertas (dispositivo_id, tipo) where reconocida_en is null;

-- Estado de histéresis por máscara y tipo de alerta (para no repetir alertas en cada lectura).
create table if not exists estado_alerta (
    dispositivo_id     uuid not null references dispositivos(id),
    tipo               text not null,
    nivel              text check (nivel in ('AVISO', 'CRITICA')),
    ultima_alerta_en   timestamptz,
    primary key (dispositivo_id, tipo)
);

-- Vista: última lectura por máscara, con la sesión abierta y el brigadista asignado.
create or replace view ultimo_estado as
select distinct on (d.id)
    d.codigo              as dispositivo,
    b.seudonimo           as brigadista,
    s.id                  as sesion_id,
    l.ts_recepcion,
    l.co_ppm,
    l.o2_pct,
    l.presion_bar,
    l.filtro_ok,
    l.bateria_pct,
    l.alarma_local
from dispositivos d
left join lecturas l on l.dispositivo_id = d.id
left join sesiones s on s.dispositivo_id = d.id and s.fin is null
left join brigadistas b on b.id = s.brigadista_id
order by d.id, l.ts_recepcion desc nulls last;

-- Revisión de silencio: una máscara con sesión abierta que lleva más de 60 s sin lecturas
-- genera una alerta SIN_SENAL (no repetida durante 5 minutos si ya hay una sin reconocer).
create or replace function revisar_silencio() returns integer
language plpgsql as $$
declare
    n integer := 0;
begin
    insert into alertas (dispositivo_id, sesion_id, tipo, nivel, valor, umbral)
    select s.dispositivo_id, s.id, 'SIN_SENAL', 'CRITICA',
           extract(epoch from now() - max(l.ts_recepcion)), 60
    from sesiones s
    join lecturas l on l.sesion_id = s.id
    where s.fin is null
    group by s.id, s.dispositivo_id
    having max(l.ts_recepcion) < now() - interval '60 seconds'
       and not exists (
           select 1 from alertas a
           where a.sesion_id = s.id and a.tipo = 'SIN_SENAL'
             and a.reconocida_en is null and a.creada_en > now() - interval '5 minutes');
    get diagnostics n = row_count;
    return n;
end $$;

-- Programar la revisión cada minuto con pg_cron (disponible en Supabase).
-- Si la extensión no está habilitada, este bloque avisa y no falla.
do $$
begin
    create extension if not exists pg_cron;
    perform cron.schedule('respira-revisar-silencio', '* * * * *', 'select revisar_silencio()');
exception when others then
    raise notice 'pg_cron no disponible (%). Habilítelo en Database > Extensions y ejecute: select cron.schedule(''respira-revisar-silencio'', ''* * * * *'', ''select revisar_silencio()'');', sqlerrm;
end $$;
