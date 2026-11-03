"""Reglas de alerta de Respira +. Funciones puras, sin base de datos.

Cada regla define el campo que se evalúa, la dirección (alto: alerta si el valor sube;
bajo: alerta si baja) y los niveles ordenados de más a menos severo.

Histéresis: una vez activa una alerta, solo se rearma cuando el valor vuelve dentro del
margen del 10 % del umbral de AVISO. Mientras la condición siga activa, la alerta se
repite como máximo cada 60 segundos.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

RANK = {"AVISO": 1, "CRITICA": 2}
REPETICION = timedelta(seconds=60)
MARGEN_REARME = 0.10


@dataclass(frozen=True)
class Regla:
    tipo: str
    campo: str
    direccion: str  # "alto" o "bajo"
    niveles: tuple  # ((nivel, umbral), ...) del más severo al menos severo


REGLAS = (
    Regla("CO_ALTO", "co_ppm", "alto", (("CRITICA", 200.0), ("AVISO", 35.0))),
    Regla("O2_BAJO", "o2_pct", "bajo", (("AVISO", 19.5),)),
    Regla("PRESION_BAJA", "presion_bar", "bajo", (("AVISO", 50.0),)),
    Regla("BATERIA_BAJA", "bateria_pct", "bajo", (("AVISO", 20.0),)),
)


def _cumple(valor: float, umbral: float, direccion: str) -> bool:
    return valor >= umbral if direccion == "alto" else valor <= umbral


def nivel_actual(valor: float, regla: Regla):
    """Devuelve (nivel, umbral) del nivel más severo que se cumple, o (None, None)."""
    for nivel, umbral in regla.niveles:
        if _cumple(valor, umbral, regla.direccion):
            return nivel, umbral
    return None, None


def fuera_de_margen(valor: float, regla: Regla) -> bool:
    """True si el valor ya volvió lo suficiente como para rearmar la alerta."""
    umbral_aviso = regla.niveles[-1][1]
    if regla.direccion == "alto":
        return valor < umbral_aviso * (1 - MARGEN_REARME)
    return valor > umbral_aviso * (1 + MARGEN_REARME)


@dataclass(frozen=True)
class Estado:
    nivel: str | None = None
    ultima_alerta_en: datetime | None = None


@dataclass(frozen=True)
class Alerta:
    tipo: str
    nivel: str
    valor: float
    umbral: float
    ocurrida_en: datetime


def decidir(valor: float, regla: Regla, estado: Estado, ahora: datetime):
    """Evalúa una lectura. Devuelve (nuevo_estado, alerta_o_None)."""
    nivel, umbral = nivel_actual(valor, regla)

    if nivel is None:
        if estado.nivel is not None and fuera_de_margen(valor, regla):
            return Estado(None, None), None
        return estado, None

    rango_nuevo = RANK[nivel]
    rango_actual = RANK.get(estado.nivel, 0)

    if rango_nuevo > rango_actual:
        # Cruce nuevo o escalada de AVISO a CRITICA: alerta inmediata.
        nuevo = Estado(nivel, ahora)
        return nuevo, Alerta(regla.tipo, nivel, valor, umbral, ahora)

    if rango_nuevo == rango_actual and estado.ultima_alerta_en is not None \
            and ahora - estado.ultima_alerta_en >= REPETICION:
        # Condición sostenida: repetir como máximo cada 60 s.
        nuevo = Estado(nivel, ahora)
        return nuevo, Alerta(regla.tipo, nivel, valor, umbral, ahora)

    # Nivel menor que el ya activo, o dentro del tiempo de repetición: sin alerta nueva.
    return estado, None
