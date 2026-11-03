"""Envío de alertas a Telegram. Si no hay credenciales configuradas, solo registra en el log."""

import logging
import os

import httpx

log = logging.getLogger("respira.alertas")

ETIQUETAS = {
    "CO_ALTO": "Monóxido de carbono alto",
    "O2_BAJO": "Oxígeno bajo",
    "PRESION_BAJA": "Presión de cilindro baja",
    "BATERIA_BAJA": "Batería baja",
    "SIN_SENAL": "Sin señal de la máscara",
    "SIN_ASIGNAR": "Máscara sin brigadista asignado",
}


def formatear(dispositivo: str, brigadista: str | None, alerta: dict) -> str:
    etiqueta = ETIQUETAS.get(alerta["tipo"], alerta["tipo"])
    quien = brigadista or "sin asignar"
    return (
        f"[{alerta['nivel']}] {etiqueta}\n"
        f"Máscara: {dispositivo} | Brigadista: {quien}\n"
        f"Valor: {alerta['valor']} | Umbral: {alerta['umbral']}"
    )


def notificar_alerta(dispositivo: str, brigadista: str | None, alerta: dict) -> None:
    texto = formatear(dispositivo, brigadista, alerta)
    log.warning(texto.replace("\n", " "))

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    respuesta = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": texto},
        timeout=10,
    )
    respuesta.raise_for_status()
