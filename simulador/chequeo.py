"""Chequeo de punta a punta contra el servicio desplegado.

Prueba: salud del servicio, envío válido, reenvío duplicado, token malo, brigadista
desconocido, valor fuera de rango, alerta de CO y estado final. Si se pasa DATABASE_URL,
también revisa las alertas directamente en la base.

Uso (desde la carpeta simulador, con el venv de ingesta):
  python chequeo.py --url https://respira-ingesta.onrender.com --token <TOKEN> \
      --brigadista B-017 [--database-url postgresql://...]

Crea datos de prueba en la base indicada. Úsalo solo contra una base de pruebas.
"""

import argparse
import os
import random
import sys
import time

import httpx


def lectura(seq, co=12.0):
    return {"seq": seq, "epoch_s": int(time.time()), "co_ppm": co, "o2_pct": 20.8,
            "presion_bar": 250.0, "filtro_ok": True, "bateria_pct": 90,
            "alarma_local": False, "lat": None, "lon": None}


def main():
    p = argparse.ArgumentParser(description="Chequeo de Respira + en producción")
    p.add_argument("--url", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--dispositivo", default="RESP-0001")
    p.add_argument("--brigadista", default="B-017")
    p.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = p.parse_args()

    fallos = []

    def check(nombre, cumple, detalle=""):
        estado = "OK  " if cumple else "FALLA"
        print(f"[{estado}] {nombre} {detalle}")
        if not cumple:
            fallos.append(nombre)

    base = args.url.rstrip("/")
    cliente = httpx.Client(timeout=30)
    boot = random.randint(1000, 999999)  # boot nuevo: evita choques con pruebas previas
    headers = {"X-Device-Token": args.token}

    r = cliente.get(f"{base}/health")
    check("health responde 200", r.status_code == 200, r.text)

    lote = {"dispositivo": args.dispositivo, "boot_id": boot, "brigadista": args.brigadista,
            "lote": [lectura(i) for i in range(1, 6)]}
    r = cliente.post(f"{base}/v1/lecturas", json=lote, headers=headers)
    check("lote válido se acepta", r.status_code == 200 and r.json()["aceptadas"] == 5, r.text)

    r = cliente.post(f"{base}/v1/lecturas", json=lote, headers=headers)
    check("reenvío se ignora como duplicado", r.status_code == 200 and r.json()["duplicadas"] == 5, r.text)

    r = cliente.post(f"{base}/v1/lecturas", json=lote, headers={"X-Device-Token": "malo"})
    check("token incorrecto da 401", r.status_code == 401, r.text)

    malo = dict(lote, brigadista="B-999", boot_id=boot + 1)
    r = cliente.post(f"{base}/v1/lecturas", json=malo, headers=headers)
    check("brigadista desconocido da 422", r.status_code == 422, r.text)

    fuera = dict(lote, boot_id=boot + 2, lote=[lectura(1, co=-5)])
    r = cliente.post(f"{base}/v1/lecturas", json=fuera, headers=headers)
    check("valor negativo de CO da 422", r.status_code == 422)

    alerta = dict(lote, boot_id=boot + 3, lote=[lectura(1, co=250.0)])
    r = cliente.post(f"{base}/v1/lecturas", json=alerta, headers=headers)
    check("CO de 250 ppm se acepta y genera alerta", r.status_code == 200, r.text)

    estado = cliente.get(f"{base}/v1/estado")
    filas = estado.json() if estado.status_code == 200 else []
    check("/v1/estado muestra la máscara",
          any(f["dispositivo"] == args.dispositivo for f in filas), estado.text[:200])

    if args.database_url:
        import psycopg
        with psycopg.connect(args.database_url) as conn:
            tipos = conn.execute(
                "select tipo, nivel from alertas where creada_en > now() - interval '5 minutes' "
                "order by id").fetchall()
        check("se creó alerta CRITICA por CO de 250",
              ("CO_ALTO", "CRITICA") in tipos, str(tipos))
        check("alerta de AVISO previa no se duplica",
              sum(1 for t in tipos if t == ("CO_ALTO", "AVISO")) <= 1, str(tipos))

    print()
    if fallos:
        print(f"{len(fallos)} chequeo(s) fallaron: {', '.join(fallos)}")
        return 1
    print("Todos los chequeos pasaron.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
