"""Simulador de una máscara Respira +. Envía lotes con el mismo contrato que usará el ESP32.

Uso:
  python simular.py --url http://localhost:8000 --dispositivo RESP-0001 \
      --token TOKEN --brigadista B-017 --lecturas 120 --pico-co 60

Simula CO subiendo y bajando (rampa), con batería que baja lentamente.
Requiere: pip install httpx
"""

import argparse
import math
import random
import time

import httpx


def generar(n: int, pico_co: float, seq_inicial: int):
    lecturas = []
    for i in range(n):
        # Onda suave: sube hasta pico_co a mitad de la simulación y vuelve a bajar.
        fase = math.sin(math.pi * i / max(n - 1, 1))
        co = max(0.0, fase * pico_co + random.uniform(-1.5, 1.5))
        lecturas.append({
            "seq": seq_inicial + i,
            "epoch_s": int(time.time()),
            "co_ppm": round(co, 2),
            "o2_pct": round(20.9 - 0.02 * i, 2),
            "presion_bar": round(max(0.0, 300.0 - 0.5 * i), 1),
            "filtro_ok": True,
            "bateria_pct": max(0, 95 - i // 20),
            "alarma_local": co >= 200,
            "lat": None,
            "lon": None,
        })
    return lecturas


def main():
    p = argparse.ArgumentParser(description="Simulador de máscara Respira +")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--dispositivo", default="RESP-0001")
    p.add_argument("--token", required=True)
    p.add_argument("--brigadista", default="B-017", help="vacío para simular máscara sin asignar")
    p.add_argument("--boot-id", type=int, default=1)
    p.add_argument("--lecturas", type=int, default=60)
    p.add_argument("--lote", type=int, default=10, help="lecturas por lote")
    p.add_argument("--pico-co", type=float, default=60.0)
    p.add_argument("--pausa", type=float, default=0.5, help="segundos entre lotes")
    args = p.parse_args()

    brigadista = args.brigadista or None
    generadas = generar(args.lecturas, args.pico_co, seq_inicial=1)
    with httpx.Client(timeout=10) as cliente:
        for i in range(0, len(generadas), args.lote):
            cuerpo = {
                "dispositivo": args.dispositivo,
                "boot_id": args.boot_id,
                "brigadista": brigadista,
                "lote": generadas[i:i + args.lote],
            }
            r = cliente.post(f"{args.url}/v1/lecturas", json=cuerpo,
                             headers={"X-Device-Token": args.token})
            print(r.status_code, r.text)
            r.raise_for_status()
            time.sleep(args.pausa)


if __name__ == "__main__":
    main()
