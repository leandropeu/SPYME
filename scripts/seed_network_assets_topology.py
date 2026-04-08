from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.security import encrypt_secret  # noqa: E402


DB_PATH = ROOT / "backend" / "data" / "spygym.db"


TOPOLOGY = [
    {
        "name": "Operadora Homero",
        "asset_type": "operator-router",
        "host": "192.168.100.1",
        "port": 80,
        "protocol": "http",
        "username": "admin",
        "password": None,
        "vendor": "Operadora",
        "model": "ONT XPTO",
        "mac_address": "AA:BB:CC:DD:EE:02",
        "local_network": "192.168.100.0/24",
        "notes": "Equipamento entregue pela operadora",
        "parent": None,
        "is_active": 1,
    },
    {
        "name": "MikroTik Homero",
        "asset_type": "mikrotik",
        "host": "10.0.7.1",
        "port": 8291,
        "protocol": "winbox",
        "username": "admin",
        "password": None,
        "vendor": "MikroTik",
        "model": "RB4011",
        "mac_address": "AA:BB:CC:DD:EE:01",
        "local_network": "10.0.7.0/24",
        "notes": "Gateway principal",
        "parent": "Operadora Homero",
        "is_active": 1,
    },
    {
        "name": "Switch Recepcao",
        "asset_type": "switch",
        "host": "10.0.7.2",
        "port": 443,
        "protocol": "https",
        "username": "admin",
        "password": None,
        "vendor": "TP-Link",
        "model": "TL-SG2210",
        "mac_address": "AA:BB:CC:DD:EE:03",
        "local_network": "10.0.7.0/24",
        "notes": "Switch principal da recepcao",
        "parent": "MikroTik Homero",
        "is_active": 1,
    },
    {
        "name": "Facial Entrada",
        "asset_type": "facial",
        "host": "10.0.7.20",
        "port": 443,
        "protocol": "https",
        "username": "admin",
        "password": None,
        "vendor": "ControlID",
        "model": "iDFace",
        "mac_address": "AA:BB:CC:DD:EE:20",
        "local_network": "10.0.7.0/24",
        "notes": "Facial da recepcao principal",
        "parent": "Switch Recepcao",
        "is_active": 1,
    },
    {
        "name": "PC Recepcao",
        "asset_type": "machine",
        "host": "10.0.7.30",
        "port": 3389,
        "protocol": "rdp",
        "username": "Administrador",
        "password": None,
        "vendor": "Dell",
        "model": "OptiPlex",
        "mac_address": "AA:BB:CC:DD:EE:30",
        "local_network": "10.0.7.0/24",
        "notes": "Computador da recepcao",
        "parent": "Switch Recepcao",
        "is_active": 1,
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Faz upsert da topologia base de ativos de rede para uma unidade.")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--unit-code", default="07")
    args = parser.parse_args()

    with sqlite3.connect(args.db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row["name"] for row in conn.execute("pragma table_info(network_assets)")}
        unit = conn.execute("select id, code, name from units where code = ?", (args.unit_code,)).fetchone()
        if not unit:
            raise SystemExit(f"Unidade nao encontrada: {args.unit_code}")

        asset_ids: dict[str, int] = {}
        for asset in TOPOLOGY:
            encrypted = encrypt_secret(asset["password"])
            existing = conn.execute(
                "select id from network_assets where unit_id = ? and name = ?",
                (unit["id"], asset["name"]),
            ).fetchone()
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            values = {
                "dvr_id": None,
                "name": asset["name"],
                "asset_type": asset["asset_type"],
                "vendor": asset["vendor"],
                "model": asset["model"],
                "host": asset["host"],
                "port": asset["port"],
                "protocol": asset["protocol"],
                "username": asset["username"],
                "password_encrypted": encrypted,
                "path": None,
                "mac_address": asset["mac_address"],
                "local_network": asset["local_network"],
                "notes": asset["notes"],
                "is_active": asset["is_active"],
                "unit_id": unit["id"],
                "status": "unknown",
                "created_at": now,
                "updated_at": now,
            }
            filtered = {key: value for key, value in values.items() if key in columns}

            if existing:
                assignments = ", ".join(f"{key} = ?" for key in filtered)
                conn.execute(
                    f"update network_assets set {assignments} where id = ?",
                    list(filtered.values()) + [existing["id"]],
                )
                asset_id = existing["id"]
                print(f"[update] {asset['name']}")
            else:
                insert_columns = ", ".join(filtered)
                placeholders = ", ".join("?" for _ in filtered)
                conn.execute(
                    f"insert into network_assets ({insert_columns}) values ({placeholders})",
                    list(filtered.values()),
                )
                asset_id = int(conn.execute("select last_insert_rowid()").fetchone()[0])
                print(f"[insert] {asset['name']}")

            asset_ids[asset["name"]] = asset_id

        if "parent_asset_id" in columns:
            for asset in TOPOLOGY:
                if not asset["parent"]:
                    continue
                now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    "update network_assets set parent_asset_id = ?, updated_at = ? where id = ?",
                    (asset_ids[asset["parent"]], now, asset_ids[asset["name"]]),
                )

        conn.commit()

        print("---")
        rows = conn.execute(
            """
            select a.name, a.asset_type, a.host, a.protocol, coalesce(parent.name, '') as parent_name
            from network_assets a
            left join network_assets parent on parent.id = a.parent_asset_id
            where a.unit_id = ?
            order by a.name
            """,
            (unit["id"],),
        ).fetchall()
        for row in rows:
            print(f"{row['name']} | {row['asset_type']} | {row['host']} | {row['protocol']} | parent={row['parent_name']}")


if __name__ == "__main__":
    main()
