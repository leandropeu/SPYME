from __future__ import annotations

import sqlite3

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import DB_PATH


DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


@event.listens_for(engine.sync_engine, "connect")
def configure_sqlite(connection: sqlite3.Connection, _) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


async def get_db():
    async with SessionLocal() as session:
        yield session


async def _run_sqlite_migrations() -> None:
    async def get_columns(conn, table_name: str) -> set[str]:
        rows = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        return {row[1] for row in rows.fetchall()}

    async def ensure_column(conn, table_name: str, column_name: str, column_sql: str) -> None:
        columns = await get_columns(conn, table_name)
        if column_name not in columns:
            await conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS cloud_accounts (
                id INTEGER PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                vendor VARCHAR(40) NOT NULL,
                email VARCHAR(160) NOT NULL,
                password_enc TEXT NOT NULL,
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY,
                occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                action VARCHAR(40) NOT NULL,
                entity VARCHAR(40) NOT NULL,
                entity_id VARCHAR(40),
                user_id INTEGER,
                user_email VARCHAR(160),
                detail TEXT,
                before_json TEXT,
                after_json TEXT
            )
            """
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_cloud_accounts_id ON cloud_accounts (id)"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_dvrs_cloud_account_id ON dvrs (cloud_account_id)"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_audit_logs_occurred_at ON audit_logs (occurred_at)"
        )
        await conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS network_assets (
                id INTEGER PRIMARY KEY,
                unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
                dvr_id INTEGER REFERENCES dvrs(id) ON DELETE SET NULL,
                name VARCHAR(120) NOT NULL,
                asset_type VARCHAR(40) NOT NULL DEFAULT 'device',
                vendor VARCHAR(80),
                model VARCHAR(120),
                host VARCHAR(120) NOT NULL,
                port INTEGER,
                protocol VARCHAR(20) NOT NULL DEFAULT 'https',
                username VARCHAR(120),
                password_encrypted TEXT,
                path VARCHAR(255),
                mac_address VARCHAR(32),
                local_network VARCHAR(64),
                notes TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_network_asset_unit_name ON network_assets (unit_id, name)"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_network_assets_id ON network_assets (id)"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_network_assets_unit_id ON network_assets (unit_id)"
        )

        for table_name, columns in {
            "users": {
                "full_name": "VARCHAR(120) DEFAULT ''",
                "role": "VARCHAR(20) DEFAULT 'viewer'",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
                "last_login_at": "DATETIME",
            },
            "auth_tokens": {
                "revoked_at": "DATETIME",
                "last_seen_at": "DATETIME",
            },
            "units": {
                "manager_name": "VARCHAR(120)",
                "manager_phone": "VARCHAR(40)",
                "network_label": "VARCHAR(120)",
                "vpn_type": "VARCHAR(40)",
                "vpn_host": "VARCHAR(120)",
                "vpn_port": "INTEGER",
                "vpn_username": "VARCHAR(120)",
                "vpn_password_encrypted": "TEXT",
                "vpn_psk_encrypted": "TEXT",
                "vpn_network_cidr": "VARCHAR(64)",
                "vpn_adapter_name": "VARCHAR(120)",
                "notes": "TEXT",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            },
            "dvrs": {
                "model": "VARCHAR(120)",
                "serial_number": "VARCHAR(120)",
                "protocol": "VARCHAR(8) DEFAULT 'http'",
                "username": "VARCHAR(80) DEFAULT 'admin'",
                "password_encrypted": "TEXT",
                "channel_count": "INTEGER NOT NULL DEFAULT 8",
                "api_status_path": "VARCHAR(255)",
                "device_info_path": "VARCHAR(255)",
                "notes": "TEXT",
                "status": "VARCHAR(20) DEFAULT 'unknown'",
                "last_seen": "DATETIME",
                "last_checked": "DATETIME",
                "last_latency_ms": "FLOAT",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
                "cloud_account_id": "INTEGER",
                "device_serial": "VARCHAR(120)",
            },
            "cameras": {
                "vendor": "VARCHAR(40) DEFAULT 'hikvision'",
                "model": "VARCHAR(120)",
                "location": "VARCHAR(120)",
                "resolution": "VARCHAR(40)",
                "snapshot_path": "VARCHAR(255)",
                "snapshot_url": "VARCHAR(500)",
                "stream_path": "VARCHAR(255)",
                "stream_url": "VARCHAR(500)",
                "notes": "TEXT",
                "status": "VARCHAR(20) DEFAULT 'unknown'",
                "last_seen": "DATETIME",
                "last_checked": "DATETIME",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            },
            "monitoring_events": {
                "source_type": "VARCHAR(20) DEFAULT 'dvr'",
                "metadata_json": "TEXT",
                "resolved_at": "DATETIME",
                "duration_seconds": "FLOAT",
                "is_resolved": "BOOLEAN NOT NULL DEFAULT 0",
            },
            "backup_records": {
                "file_size": "INTEGER",
                "error_message": "TEXT",
                "completed_at": "DATETIME",
                "retained_until": "DATETIME",
            },
            "network_assets": {
                "dvr_id": "INTEGER",
                "asset_type": "VARCHAR(40) NOT NULL DEFAULT 'device'",
                "vendor": "VARCHAR(80)",
                "model": "VARCHAR(120)",
                "port": "INTEGER",
                "protocol": "VARCHAR(20) NOT NULL DEFAULT 'https'",
                "username": "VARCHAR(120)",
                "password_encrypted": "TEXT",
                "path": "VARCHAR(255)",
                "mac_address": "VARCHAR(32)",
                "local_network": "VARCHAR(64)",
                "notes": "TEXT",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
                "created_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
            },
        }.items():
            for column_name, column_sql in columns.items():
                await ensure_column(conn, table_name, column_name, column_sql)


async def init_db() -> None:
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _run_sqlite_migrations()
