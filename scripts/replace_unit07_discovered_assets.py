from __future__ import annotations

import sqlite3
from datetime import datetime, UTC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"


DISCOVERED_ASSETS = [
    {
        "name": "MikroTik HTHON",
        "asset_type": "mikrotik",
        "vendor": "MikroTik",
        "model": "hEX",
        "host": "10.0.7.1",
        "port": 8291,
        "protocol": "winbox",
        "username": None,
        "path": None,
        "local_network": "10.0.7.0/24",
        "notes": "Gateway principal validado pela VPN OpenVPN em 2026-04-07.",
        "parent": None,
        "dvr_host": None,
    },
    {
        "name": "Host Windows 10.0.7.5",
        "asset_type": "machine",
        "vendor": "Microsoft",
        "model": "Windows Host",
        "host": "10.0.7.5",
        "port": 80,
        "protocol": "http",
        "username": None,
        "path": None,
        "local_network": "10.0.7.0/24",
        "notes": "Host descoberto no scan. Portas abertas: 80, 139, 445.",
        "parent": "MikroTik HTHON",
        "dvr_host": None,
    },
    {
        "name": "Dispositivo DNS/Web 10.0.7.6",
        "asset_type": "network-device",
        "vendor": "Desconhecido",
        "model": "dnsmasq/lighttpd",
        "host": "10.0.7.6",
        "port": 80,
        "protocol": "http",
        "username": None,
        "path": None,
        "local_network": "10.0.7.0/24",
        "notes": "Host descoberto no scan. Servicos identificados: dnsmasq 2.79 e lighttpd 1.4.51.",
        "parent": "MikroTik HTHON",
        "dvr_host": None,
    },
    {
        "name": "DVR Hikvision 10.0.7.251",
        "asset_type": "dvr",
        "vendor": "Hikvision",
        "model": "DVR/NVR",
        "host": "10.0.7.251",
        "port": 8000,
        "protocol": "hikvision-sdk",
        "username": None,
        "path": None,
        "local_network": "10.0.7.0/24",
        "notes": "DVR validado por HTTP/HTTPS/RTSP/porta 8000 no scan via VPN.",
        "parent": "MikroTik HTHON",
        "dvr_host": "10.0.7.251",
    },
    {
        "name": "Host Desconhecido 10.0.7.252",
        "asset_type": "unknown",
        "vendor": "Desconhecido",
        "model": "Host ativo",
        "host": "10.0.7.252",
        "port": None,
        "protocol": "icmp",
        "username": None,
        "path": None,
        "local_network": "10.0.7.0/24",
        "notes": "Host responde ao scan, mas as portas comuns testadas apareceram fechadas.",
        "parent": "MikroTik HTHON",
        "dvr_host": None,
    },
]


def main() -> None:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        unit = conn.execute("select id, name from units where code = '07'").fetchone()
        if not unit:
            raise SystemExit("Unidade 07 nao encontrada.")

        # Replace only the current unit-07 topology so the map reflects the real scan.
        conn.execute("delete from network_assets where unit_id = ?", (unit["id"],))

        asset_ids: dict[str, int] = {}
        for asset in DISCOVERED_ASSETS:
            dvr_id = None
            if asset["dvr_host"]:
                dvr = conn.execute(
                    "select id from dvrs where unit_id = ? and host = ?",
                    (unit["id"], asset["dvr_host"]),
                ).fetchone()
                dvr_id = dvr["id"] if dvr else None

            conn.execute(
                """
                insert into network_assets (
                    unit_id, dvr_id, name, asset_type, vendor, model, host, port, protocol,
                    username, password_encrypted, path, mac_address, local_network, status,
                    last_seen, last_checked, last_latency_ms, notes, is_active, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit["id"],
                    dvr_id,
                    asset["name"],
                    asset["asset_type"],
                    asset["vendor"],
                    asset["model"],
                    asset["host"],
                    asset["port"],
                    asset["protocol"],
                    asset["username"],
                    None,
                    asset["path"],
                    None,
                    asset["local_network"],
                    "online" if asset["host"] in {"10.0.7.1", "10.0.7.5", "10.0.7.6", "10.0.7.251", "10.0.7.252"} else "unknown",
                    now,
                    now,
                    None,
                    asset["notes"],
                    1,
                    now,
                    now,
                ),
            )
            asset_ids[asset["name"]] = int(conn.execute("select last_insert_rowid()").fetchone()[0])

        for asset in DISCOVERED_ASSETS:
            if not asset["parent"]:
                continue
            conn.execute(
                "update network_assets set parent_asset_id = ?, updated_at = ? where id = ?",
                (asset_ids[asset["parent"]], now, asset_ids[asset["name"]]),
            )

        conn.commit()

        rows = conn.execute(
            """
            select name, asset_type, host, protocol, status
            from network_assets
            where unit_id = ?
            order by host
            """,
            (unit["id"],),
        ).fetchall()

    print(f"Topologia real da unidade 07 aplicada. Registros: {len(rows)}")
    for row in rows:
        print(f"{row['host']} | {row['name']} | {row['asset_type']} | {row['protocol']} | {row['status']}")


if __name__ == "__main__":
    main()
