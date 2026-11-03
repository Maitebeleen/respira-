"""Lógica de ingesta: recibe un lote, lo guarda sin duplicar y evalúa las alertas."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

from .reglas import REGLAS, Alerta, Estado, decidir

INACTIVIDAD_CIERRE = timedelta(minutes=15)
ALERTA_SIN_ASIGNAR_CADA = timedelta(minutes=10)


class ErrorIngesta(Exception):
    """Error de validación que se traduce a una respuesta HTTP 4xx."""

    def __init__(self, status: int, detalle: str):
        super().__init__(detalle)
        self.status = status
        self.detalle = detalle


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def procesar_lote(conn: psycopg.Connection, token: str, lote) -> dict:
    """Procesa un lote dentro de una transacción. Devuelve el resumen y las alertas nuevas."""
    ahora = datetime.now(timezone.utc)
    alertas_nuevas: list[dict] = []

    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        # 1. Autenticar el dispositivo.
        cur.execute("select id, token_hash from dispositivos where codigo = %s", (lote.dispositivo,))
        disp = cur.fetchone()
        if disp is None or not hmac.compare_digest(disp["token_hash"], hash_token(token)):
            raise ErrorIngesta(401, "dispositivo o token inválidos")
        dispositivo_id = disp["id"]

        # 2. Resolver el brigadista (si el lote lo trae).
        brigadista_id = None
        if lote.brigadista is not None:
            cur.execute(
                "select id from brigadistas where seudonimo = %s and activo",
                (lote.brigadista,),
            )
            fila = cur.fetchone()
            if fila is None:
                raise ErrorIngesta(422, f"brigadista desconocido: {lote.brigadista}")
            brigadista_id = fila["id"]

        # 3. Gestionar la sesión abierta.
        sesion_id = _gestionar_sesion(cur, dispositivo_id, brigadista_id, ahora)

        # 4. Insertar lecturas sin duplicar.
        insertadas = []
        for lectura in sorted(lote.lote, key=lambda x: x.seq):
            ts_disp = (
                datetime.fromtimestamp(lectura.epoch_s, tz=timezone.utc)
                if lectura.epoch_s is not None else None
            )
            cur.execute(
                """
                insert into lecturas (dispositivo_id, sesion_id, boot_id, seq, ts_dispositivo,
                    ts_recepcion, co_ppm, o2_pct, presion_bar, filtro_ok, bateria_pct,
                    alarma_local, lat, lon)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (dispositivo_id, boot_id, seq) do nothing
                returning id, co_ppm, o2_pct, presion_bar, bateria_pct
                """,
                (dispositivo_id, sesion_id, lote.boot_id, lectura.seq, ts_disp, ahora,
                 lectura.co_ppm, lectura.o2_pct, lectura.presion_bar, lectura.filtro_ok,
                 lectura.bateria_pct, lectura.alarma_local, lectura.lat, lectura.lon),
            )
            fila = cur.fetchone()
            if fila is not None:
                insertadas.append(fila)

        # 5. Evaluar reglas sobre las lecturas nuevas (las duplicadas no se reevalúan).
        if insertadas:
            cur.execute(
                "select tipo, nivel, ultima_alerta_en from estado_alerta where dispositivo_id = %s",
                (dispositivo_id,),
            )
            estados = {
                f["tipo"]: Estado(f["nivel"], f["ultima_alerta_en"]) for f in cur.fetchall()
            }

            for fila in insertadas:
                for regla in REGLAS:
                    valor = fila[regla.campo]
                    if valor is None:
                        continue
                    estado = estados.get(regla.tipo, Estado())
                    nuevo, alerta = decidir(float(valor), regla, estado, ahora)
                    estados[regla.tipo] = nuevo
                    if alerta is not None:
                        alertas_nuevas.append(
                            _guardar_alerta(cur, dispositivo_id, sesion_id, alerta)
                        )

            for tipo, est in estados.items():
                cur.execute(
                    """
                    insert into estado_alerta (dispositivo_id, tipo, nivel, ultima_alerta_en)
                    values (%s, %s, %s, %s)
                    on conflict (dispositivo_id, tipo)
                    do update set nivel = excluded.nivel, ultima_alerta_en = excluded.ultima_alerta_en
                    """,
                    (dispositivo_id, tipo, est.nivel, est.ultima_alerta_en),
                )

        # 6. Lecturas sin brigadista: avisar, sin repetir cada pocos segundos.
        if insertadas and sesion_id is None:
            cur.execute(
                """
                select 1 from alertas
                where dispositivo_id = %s and tipo = 'SIN_ASIGNAR' and creada_en > %s
                """,
                (dispositivo_id, ahora - ALERTA_SIN_ASIGNAR_CADA),
            )
            if cur.fetchone() is None:
                alertas_nuevas.append(
                    _guardar_alerta(
                        cur, dispositivo_id, None,
                        Alerta("SIN_ASIGNAR", "AVISO", 0.0, 0.0, ahora),
                    )
                )

        ultimo_seq = max(l.seq for l in lote.lote)

    return {
        "aceptadas": len(insertadas),
        "duplicadas": len(lote.lote) - len(insertadas),
        "ultimo_seq": ultimo_seq,
        "alertas": alertas_nuevas,
    }


def _gestionar_sesion(cur, dispositivo_id, brigadista_id, ahora):
    """Devuelve el id de la sesión que deben usar las lecturas del lote, o None."""
    cur.execute(
        """
        select s.id, s.brigadista_id,
               (select max(ts_recepcion) from lecturas l where l.sesion_id = s.id) as ultima
        from sesiones s
        where s.dispositivo_id = %s and s.fin is null
        """,
        (dispositivo_id,),
    )
    activa = cur.fetchone()

    if activa is not None:
        inactiva = activa["ultima"] is not None and ahora - activa["ultima"] > INACTIVIDAD_CIERRE
        mismo = brigadista_id is not None and activa["brigadista_id"] == brigadista_id
        if mismo and not inactiva:
            return activa["id"]
        cur.execute("update sesiones set fin = %s where id = %s", (ahora, activa["id"]))

    if brigadista_id is None:
        return None

    cur.execute(
        "insert into sesiones (dispositivo_id, brigadista_id, inicio) values (%s, %s, %s) returning id",
        (dispositivo_id, brigadista_id, ahora),
    )
    return cur.fetchone()["id"]


def _guardar_alerta(cur, dispositivo_id, sesion_id, alerta: Alerta) -> dict:
    cur.execute(
        """
        insert into alertas (dispositivo_id, sesion_id, tipo, nivel, valor, umbral, creada_en)
        values (%s, %s, %s, %s, %s, %s, %s) returning id
        """,
        (dispositivo_id, sesion_id, alerta.tipo, alerta.nivel, alerta.valor, alerta.umbral,
         alerta.ocurrida_en),
    )
    return {
        "id": cur.fetchone()["id"],
        "tipo": alerta.tipo,
        "nivel": alerta.nivel,
        "valor": alerta.valor,
        "umbral": alerta.umbral,
    }
