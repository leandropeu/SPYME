from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"


def ensure_column(conn: sqlite3.Connection, table: str, column_name: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if column_name in columns:
        return
    conn.execute(f"alter table {table} add column {column_name} {definition}")
    print(f"[add-column] {table}.{column_name} {definition}")


def ensure_index(conn: sqlite3.Connection, index_name: str, table: str, columns: str) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"pragma index_list({table})").fetchall()
    }
    if index_name in existing:
        return
    conn.execute(f"create index if not exists {index_name} on {table} ({columns})")
    print(f"[add-index] {index_name} on {table}({columns})")


def main() -> None:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        ensure_column(conn, "network_assets", "dvr_id", "INTEGER")
        ensure_column(conn, "network_assets", "parent_asset_id", "INTEGER")
        ensure_column(conn, "network_assets", "vendor", "VARCHAR(80)")
        ensure_column(conn, "network_assets", "model", "VARCHAR(120)")
        ensure_column(conn, "network_assets", "port", "INTEGER")
        ensure_column(conn, "network_assets", "protocol", "VARCHAR(20) DEFAULT 'https'")
        ensure_column(conn, "network_assets", "username", "VARCHAR(120)")
        ensure_column(conn, "network_assets", "password_encrypted", "TEXT")
        ensure_column(conn, "network_assets", "path", "VARCHAR(255)")
        ensure_column(conn, "network_assets", "mac_address", "VARCHAR(32)")
        ensure_column(conn, "network_assets", "local_network", "VARCHAR(64)")
        ensure_column(conn, "network_assets", "status", "VARCHAR(20) DEFAULT 'unknown'")
        ensure_column(conn, "network_assets", "last_seen", "DATETIME")
        ensure_column(conn, "network_assets", "last_checked", "DATETIME")
        ensure_column(conn, "network_assets", "last_latency_ms", "FLOAT")
        ensure_column(conn, "network_assets", "notes", "TEXT")
        ensure_column(conn, "network_assets", "is_active", "BOOLEAN DEFAULT 1")
        ensure_column(conn, "network_assets", "created_at", "DATETIME")
        ensure_column(conn, "network_assets", "updated_at", "DATETIME")

        ensure_column(conn, "monitoring_events", "network_asset_id", "INTEGER")
        ensure_column(conn, "monitoring_events", "source_type", "VARCHAR(20) DEFAULT 'dvr'")

        ensure_index(conn, "ix_network_assets_unit_id", "network_assets", "unit_id")
        ensure_index(conn, "ix_network_assets_dvr_id", "network_assets", "dvr_id")
        ensure_index(conn, "ix_network_assets_parent_asset_id", "network_assets", "parent_asset_id")
        ensure_index(conn, "ix_monitoring_events_network_asset_id", "monitoring_events", "network_asset_id")

        conn.execute(
            """
            update network_assets
            set status = coalesce(nullif(status, ''), 'unknown'),
                protocol = coalesce(nullif(protocol, ''), 'https'),
                is_active = coalesce(is_active, 1),
                created_at = coalesce(created_at, ?),
                updated_at = coalesce(updated_at, ?)
            """
            ,
            (now, now),
        )

        conn.execute(
            """
            update monitoring_events
            set source_type = coalesce(nullif(source_type, ''), 'dvr')
            """
        )

        conn.commit()

        network_cols = [row[1] for row in conn.execute("pragma table_info(network_assets)").fetchall()]
        event_cols = [row[1] for row in conn.execute("pragma table_info(monitoring_events)").fetchall()]
        print("---")
        print("network_assets:", ", ".join(network_cols))
        print("monitoring_events:", ", ".join(event_cols))


if __name__ == "__main__":
    main()
