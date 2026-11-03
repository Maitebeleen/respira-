from datetime import datetime, timedelta, timezone

from app.reglas import REGLAS, Estado, decidir

CO = next(r for r in REGLAS if r.tipo == "CO_ALTO")
T0 = datetime(2026, 11, 3, 17, 0, tzinfo=timezone.utc)


def test_debajo_del_umbral_no_alerta():
    nuevo, alerta = decidir(20.0, CO, Estado(), T0)
    assert alerta is None
    assert nuevo.nivel is None


def test_cruce_a_aviso_alerta_una_vez():
    nuevo, alerta = decidir(36.0, CO, Estado(), T0)
    assert alerta is not None and alerta.nivel == "AVISO" and alerta.umbral == 35.0
    assert nuevo.nivel == "AVISO"


def test_sostenido_no_repite_antes_de_60_segundos():
    estado = Estado("AVISO", T0)
    _, alerta = decidir(40.0, CO, estado, T0 + timedelta(seconds=30))
    assert alerta is None


def test_sostenido_repite_a_los_60_segundos():
    estado = Estado("AVISO", T0)
    nuevo, alerta = decidir(40.0, CO, estado, T0 + timedelta(seconds=60))
    assert alerta is not None and alerta.nivel == "AVISO"
    assert nuevo.ultima_alerta_en == T0 + timedelta(seconds=60)


def test_escalada_a_critica_alerta_de_inmediato():
    estado = Estado("AVISO", T0)
    nuevo, alerta = decidir(250.0, CO, estado, T0 + timedelta(seconds=5))
    assert alerta is not None and alerta.nivel == "CRITICA" and alerta.umbral == 200.0
    assert nuevo.nivel == "CRITICA"


def test_bajar_de_critica_a_aviso_no_alerta_ni_baja_el_estado():
    estado = Estado("CRITICA", T0)
    nuevo, alerta = decidir(50.0, CO, estado, T0 + timedelta(seconds=5))
    assert alerta is None
    assert nuevo.nivel == "CRITICA"


def test_histeresis_no_rearma_dentro_del_margen():
    # Umbral 35, margen 10 %: 32 ppm sigue dentro del margen, no se rearma.
    estado = Estado("AVISO", T0)
    nuevo, _ = decidir(32.0, CO, estado, T0 + timedelta(seconds=10))
    assert nuevo.nivel == "AVISO"


def test_rearma_cuando_baja_del_90_por_ciento():
    estado = Estado("AVISO", T0)
    nuevo, alerta = decidir(20.0, CO, estado, T0 + timedelta(seconds=10))
    assert nuevo.nivel is None and alerta is None


def test_nuevo_cruce_tras_rearme_alerta_otra_vez():
    estado = Estado(None, None)
    _, alerta = decidir(40.0, CO, estado, T0 + timedelta(minutes=5))
    assert alerta is not None


def test_bateria_baja_usa_direccion_bajo():
    bat = next(r for r in REGLAS if r.tipo == "BATERIA_BAJA")
    _, alerta = decidir(15.0, bat, Estado(), T0)
    assert alerta is not None and alerta.nivel == "AVISO"
    _, alerta = decidir(80.0, bat, Estado(), T0)
    assert alerta is None
