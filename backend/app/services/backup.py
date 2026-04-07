from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import BACKUP_DIR, BACKUP_MAX_FILES, BACKUP_RETENTION_DAYS, DB_PATH
from ..models import BackupRecord


BroadcastHook = Callable[[dict], Awaitable[None]]
_broadcast_hook: BroadcastHook | None = None


def set_broadcast_hook(handler: BroadcastHook | None) -> None:
    global _broadcast_hook
    _broadcast_hook = handler


async def _broadcast(payload: dict) -> None:
    if _broadcast_hook:
        await _broadcast_hook(payload)


def _perform_sqlite_backup(destination: Path) -> int:
    with sqlite3.connect(DB_PATH) as source_conn, sqlite3.connect(destination) as dest_conn:
        source_conn.backup(dest_conn)
    return destination.stat().st_size


async def cleanup_old_backups(session: AsyncSession) -> None:
    threshold = datetime.utcnow() - timedelta(days=BACKUP_RETENTION_DAYS)
    records = (
        await session.execute(select(BackupRecord).order_by(BackupRecord.started_at.desc()))
    ).scalars().all()

    for index, record in enumerate(records):
        should_remove = index >= BACKUP_MAX_FILES or record.started_at < threshold or record.status == "failed"
        if not should_remove:
            continue
        path = Path(record.file_path)
        if path.exists():
            path.unlink(missing_ok=True)
        await session.delete(record)

    await session.commit()


async def create_backup(session: AsyncSession) -> BackupRecord:
    now = datetime.utcnow()
    file_name = f"spygym_{now:%Y%m%d_%H%M%S}.sqlite3"
    destination = BACKUP_DIR / file_name

    record = BackupRecord(
        file_name=file_name,
        file_path=str(destination),
        status="running",
        started_at=now,
        retained_until=now + timedelta(days=BACKUP_RETENTION_DAYS),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)

    try:
        file_size = await asyncio.to_thread(_perform_sqlite_backup, destination)
        record.file_size = file_size
        record.status = "completed"
        record.completed_at = datetime.utcnow()
        await session.commit()
        await cleanup_old_backups(session)
        await _broadcast({"type": "backup_completed", "backup_id": record.id, "file_name": record.file_name})
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        record.completed_at = datetime.utcnow()
        await session.commit()
        await _broadcast({"type": "backup_failed", "backup_id": record.id, "file_name": record.file_name})
        raise

    return record


async def list_backups(session: AsyncSession) -> list[BackupRecord]:
    records = (
        await session.execute(select(BackupRecord).order_by(BackupRecord.started_at.desc()))
    ).scalars().all()
    return list(records)
