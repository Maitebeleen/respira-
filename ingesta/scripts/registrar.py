"""Registra máscaras y brigadistas en la base.

Uso:
  DATABASE_URL=... python scripts/registrar.py dispositivo RESP-0001 [--version 0.1.0]
  DATABASE_URL=... python scripts/registrar.py brigadista B-017

El token de la máscara se muestra una sola vez. Guárdelo en el firmware del ESP32.
"""

import argparse
import os
import secrets
import sys

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ingesta import hash_token  # noqa: E402


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="Registrar máscara o brigadista")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dispositivo")
    d.add_argument("codigo")
    d.add_argument("--version", default=None)
    b = sub.add_parser("brigadista")
    b.add_argument("seudonimo")
    args = parser.parse_args()

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        if args.cmd == "dispositivo":
            token = secrets.token_urlsafe(32)
            cur.execute(
                "insert into dispositivos (codigo, token_hash, version_firmware) values (%s, %s, %s)",
                (args.codigo, hash_token(token), args.version),
            )
            print(f"Máscara {args.codigo} registrada.")
            print(f"Token (guárdelo ahora, no se vuelve a mostrar): {token}")
        else:
            cur.execute("insert into brigadistas (seudonimo) values (%s)", (args.seudonimo,))
            print(f"Brigadista {args.seudonimo} registrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
