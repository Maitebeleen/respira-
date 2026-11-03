"""API de ingesta de Respira +. Recibe lotes de lecturas desde las máscaras."""

import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .ingesta import ErrorIngesta, procesar_lote
from .notificar import notificar_alerta

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("respira")

app = FastAPI(title="Respira + ingesta", version="0.1.0")


class Lectura(BaseModel):
    seq: int = Field(ge=0)
    epoch_s: int | None = Field(default=None, description="Unix epoch en segundos, o null sin NTP")
    co_ppm: float = Field(ge=0, le=10000)
    o2_pct: float | None = Field(default=None, ge=0, le=100)
    presion_bar: float | None = Field(default=None, ge=0, le=400)
    filtro_ok: bool | None = None
    bateria_pct: int | None = Field(default=None, ge=0, le=100)
    alarma_local: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class Lote(BaseModel):
    dispositivo: str = Field(min_length=1, max_length=64)
    boot_id: int = Field(ge=0)
    brigadista: str | None = Field(default=None, max_length=64)
    lote: list[Lectura] = Field(min_length=1, max_length=1000)


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable DATABASE_URL")
    with psycopg.connect(url) as conn:
        yield conn


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/v1/lecturas", status_code=200)
def recibir_lecturas(
    lote: Lote,
    x_device_token: str = Header(..., alias="X-Device-Token"),
    conn: psycopg.Connection = Depends(get_conn),
):
    try:
        resultado = procesar_lote(conn, x_device_token, lote)
    except ErrorIngesta as e:
        raise HTTPException(status_code=e.status, detail=e.detalle)

    for alerta in resultado.pop("alertas"):
        try:
            notificar_alerta(lote.dispositivo, lote.brigadista, alerta)
        except Exception:  # la notificación nunca debe tumbar la ingesta
            log.exception("No se pudo notificar la alerta %s", alerta.get("id"))
    return resultado


@app.get("/v1/estado")
def estado(conn: psycopg.Connection = Depends(get_conn)):
    """Último estado por máscara. Sirve para el dashboard y para probar."""
    with conn.cursor() as cur:
        cur.execute("select * from ultimo_estado order by dispositivo")
        cols = [c.name for c in cur.description]
        filas = [dict(zip(cols, fila)) for fila in cur.fetchall()]
    return JSONResponse([_serializable(f) for f in filas])


def _serializable(fila: dict) -> dict:
    salida = {}
    for k, v in fila.items():
        if isinstance(v, uuid.UUID):
            salida[k] = str(v)
        elif isinstance(v, datetime):
            salida[k] = v.isoformat()
        elif isinstance(v, Decimal):
            salida[k] = float(v)
        else:
            salida[k] = v
    return salida
