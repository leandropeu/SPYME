"""
scripts/migrate_db.py — valida e aplica migrações compatíveis no SQLite.
Uso:  py -3 scripts/migrate_db.py
"""
from __future__ import annotations
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db import SessionLocal, init_db

CHECKS = {
    "cloud_accounts": ["name", "vendor", "email", "password_enc"],
    "audit_logs": ["action", "entity", "occurred_at"],
    "dvrs": ["cloud_account_id", "device_serial", "api_status_path", "device_info_path"],
    "cameras": ["snapshot_path", "snapshot_url", "stream_path", "stream_url"],
    "monitoring_events": ["metadata_json", "duration_seconds", "is_resolved"],
}

async def migrate() -> None:
    print("\nIniciando migração...\n")
    await init_db()
    print("Estrutura principal validada.\n")

    async with SessionLocal() as session:
        for table_name, columns in CHECKS.items():
            rows = await session.execute(text(f"PRAGMA table_info({table_name})"))
            existing = {row[1] for row in rows.fetchall()}
            missing = [column for column in columns if column not in existing]
            if missing:
                print(f"   Faltando em {table_name}: {', '.join(missing)}")
            else:
                print(f"   OK {table_name}: {', '.join(columns)}")

    print("\nMigração concluída.\n")

if __name__ == "__main__":
    asyncio.run(migrate())
