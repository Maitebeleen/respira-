"""Pruebas de la API contra PostgreSQL real.

Requiere TEST_DATABASE_URL apuntando a una base DESECHABLE. Las tablas se borran al iniciar.
Ejemplo: TEST_DATABASE_URL=postgresql://postgres:test@localhost:5433/respira pytest
"""

import os
import pathlib
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.ingesta import hash_token

SCHEMA = pathlib.Path(__file__).resolve().parents[2] / "db" / "schema.sql"
TOKEN = "token-de-prueba"


@pytest.fixture()
def cliente(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL no definida")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        conn.execute(
            "insert into dispositivos (codigo, token_hash) values ('RESP-0001', %s)",
            (hash_token(TOKEN),),
        )
        conn.execute("insert into brigadistas (seudonimo) values ('B-017')")
    monkeypatch.setenv("DATABASE_URL", url)
    from app.main import app
    return TestClient(app)


def lectura(seq, co=12.0, **extra):
    base = {"seq": seq, "co_ppm": co, "o2_pct": 20.8, "presion_bar": 200.0,
            "bateria_pct": 90, "filtro_ok": True, "alarma_local": False}
    base.update(extra)
    return base


def lote(lecturas, brigadista="B-017", boot_id=1):
    return {"dispositivo": "RESP-0001", "boot_id": boot_id,
            "brigadista": brigadista, "lote": lecturas}


def enviar(cliente, cuerpo, token=TOKEN):
    return cliente.post("/v1/lecturas", json=cuerpo, headers={"X-Device-Token": token})


def test_token_incorrecto_rechazado(cliente):
    r = enviar(cliente, lote([lectura(1)]), token="malo")
    assert r.status_code == 401


def test_lote_valido_se_guarda(cliente):
    r = enviar(cliente, lote([lectura(1), lectura(2)]))
    assert r.status_code == 200
    assert r.json() == {"aceptadas": 2, "duplicadas": 0, "ultimo_seq": 2}


def test_reenvio_no_duplica(cliente):
    enviar(cliente, lote([lectura(1), lectura(2)]))
    r = enviar(cliente, lote([lectura(1), lectura(2), lectura(3)]))
    assert r.json()["aceptadas"] == 1
    assert r.json()["duplicadas"] == 2


def test_reinicio_con_nuevo_boot_id_no_descarta(cliente):
    enviar(cliente, lote([lectura(1)], boot_id=1))
    r = enviar(cliente, lote([lectura(1)], boot_id=2))
    assert r.json()["aceptadas"] == 1


def test_brigadista_desconocido_422(cliente):
    r = enviar(cliente, lote([lectura(1)], brigadista="B-999"))
    assert r.status_code == 422


def test_campo_fuera_de_rango_422(cliente):
    r = enviar(cliente, lote([lectura(1, co=-5)]))
    assert r.status_code == 422


def test_cruce_de_co_crea_una_alerta_y_no_la_repite(cliente):
    enviar(cliente, lote([lectura(1, co=40.0)]))
    enviar(cliente, lote([lectura(2, co=41.0)]))
    r = cliente.get("/v1/estado")
    assert r.status_code == 200
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        n = conn.execute(
            "select count(*) from alertas where tipo = 'CO_ALTO' and nivel = 'AVISO'"
        ).fetchone()[0]
    assert n == 1


def test_lectura_sin_brigadista_genera_sin_asignar(cliente):
    r = enviar(cliente, lote([lectura(1)], brigadista=None))
    assert r.status_code == 200
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        n = conn.execute("select count(*) from alertas where tipo = 'SIN_ASIGNAR'").fetchone()[0]
        sesiones = conn.execute("select count(*) from sesiones").fetchone()[0]
    assert n == 1 and sesiones == 0


def test_estado_muestra_brigadista_asignado(cliente):
    enviar(cliente, lote([lectura(1, co=8.0)]))
    datos = cliente.get("/v1/estado").json()
    assert datos[0]["dispositivo"] == "RESP-0001"
    assert datos[0]["brigadista"] == "B-017"
    assert datos[0]["co_ppm"] == 8.0


def test_silencio_cierra_sesion_tras_15_minutos(cliente):
    enviar(cliente, lote([lectura(1)]))
    url = os.environ["TEST_DATABASE_URL"]
    with psycopg.connect(url, autocommit=True) as conn:
        # Simular que la última lectura fue hace 20 minutos.
        conn.execute("update lecturas set ts_recepcion = now() - interval '20 minutes'")
        conn.execute("select revisar_silencio()")
        abiertas = conn.execute("select count(*) from sesiones where fin is null").fetchone()[0]
        alertas = conn.execute(
            "select count(*) from alertas where tipo = 'SIN_SENAL'").fetchone()[0]
    assert abiertas == 0
    assert alertas == 1
