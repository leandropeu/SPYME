from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.security import encrypt_secret  # noqa: E402


DB_PATH = ROOT / "backend" / "data" / "spygym.db"
DEFAULT_CSV = ROOT / "deploy" / "network-assets-import-template.csv"


def normalize_bool(value: str | None) -> int:
    return 0 if str(value or "").strip().lower() in {"0", "false", "nao", "não"} else 1


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.exists():
      raise SystemExit(f"Arquivo CSV nao encontrado: {csv_path}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8-sig").splitlines()))

        for row in rows:
            unit = conn.execute("select id from units where code = ?", (row["unit_code"],)).fetchone()
            if not unit:
                print(f"[ignorado] unidade nao encontrada: {row['unit_code']} / {row['name']}")
                continue
            dvr_id = None
            if row.get("dvr_name"):
                dvr = conn.execute("select id from dvrs where unit_id = ? and name = ?", (unit["id"], row["dvr_name"])).fetchone()
                dvr_id = dvr["id"] if dvr else None

            password_encrypted = encrypt_secret(row.get("password") or None)
            existing = conn.execute(
                "select id from network_assets where unit_id = ? and name = ?",
                (unit["id"], row["name"]),
            ).fetchone()

            payload = (
                dvr_id,
                row.get("name"),
                row.get("asset_type") or "device",
                row.get("vendor") or None,
                row.get("model") or None,
                row.get("host"),
                int(row["port"]) if row.get("port") else None,
                row.get("protocol") or "https",
                row.get("username") or None,
                password_encrypted,
                row.get("path") or None,
                row.get("mac_address") or None,
                row.get("local_network") or None,
                row.get("notes") or None,
                normalize_bool(row.get("is_active")),
                unit["id"],
            )

            if existing:
                conn.execute(
                    """
                    update network_assets
                    set dvr_id = ?, name = ?, asset_type = ?, vendor = ?, model = ?, host = ?, port = ?, protocol = ?,
                        username = ?, password_encrypted = coalesce(?, password_encrypted), path = ?, mac_address = ?,
                        local_network = ?, notes = ?, is_active = ?, unit_id = ?, updated_at = CURRENT_TIMESTAMP
                    where id = ?
                    """,
                    payload + (existing["id"],),
                )
            else:
                conn.execute(
                    """
                    insert into network_assets (
                        dvr_id, name, asset_type, vendor, model, host, port, protocol, username,
                        password_encrypted, path, mac_address, local_network, notes, is_active, unit_id
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload[:-1] + (payload[-1],),
                )

        for row in rows:
            unit = conn.execute("select id from units where code = ?", (row["unit_code"],)).fetchone()
            if not unit:
                continue
            if not row.get("parent_asset_name"):
                continue
            asset = conn.execute(
                "select id from network_assets where unit_id = ? and name = ?",
                (unit["id"], row["name"]),
            ).fetchone()
            parent = conn.execute(
                "select id from network_assets where unit_id = ? and name = ?",
                (unit["id"], row["parent_asset_name"]),
            ).fetchone()
            if asset and parent:
                conn.execute(
                    "update network_assets set parent_asset_id = ?, updated_at = CURRENT_TIMESTAMP where id = ?",
                    (parent["id"], asset["id"]),
                )

        conn.commit()
    print(f"Importacao concluida a partir de: {csv_path}")
