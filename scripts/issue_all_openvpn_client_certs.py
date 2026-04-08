from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"
EASYRSA_DIR = Path("/etc/openvpn/easy-rsa")


def main() -> None:
    if not EASYRSA_DIR.exists():
        raise SystemExit(f"Easy-RSA nao encontrado em {EASYRSA_DIR}")

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            select code, name, coalesce(nullif(vpn_username, ''), code, name) as client_cn
            from units
            where is_active = 1
            order by code
            """
        ).fetchall()

    issued = 0
    for code, name, client_cn in rows:
        print(f"[emitindo] {code} - {name} -> {client_cn}")
        subprocess.run(
            ["./easyrsa", "build-client-full", str(client_cn), "nopass"],
            cwd=EASYRSA_DIR,
            env={"EASYRSA_BATCH": "1"},
            check=True,
        )
        issued += 1

    print(f"Certificados emitidos: {issued}")


if __name__ == "__main__":
    main()
