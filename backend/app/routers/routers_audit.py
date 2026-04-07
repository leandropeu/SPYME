from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import AuditLog
from ..services.auth import ROLE_ADMIN, get_current_user, require_roles

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(get_current_user)])

_LOG_DIR = Path(os.getenv("SPYGYM_DATA_DIR", Path(__file__).resolve().parents[3] / "backend" / "data")) / "audit_logs"


@router.get("", response_model=list[dict])
async def list_audit_logs(
    entity: str | None = None,
    action: str | None = None,
    user_email: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(default=200, le=1000),
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN)),
):
    """Lista logs de auditoria com filtros opcionais. Apenas admin."""
    q = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit)

    filters = []
    if entity:      filters.append(AuditLog.entity == entity)
    if action:      filters.append(AuditLog.action == action)
    if user_email:  filters.append(AuditLog.user_email.ilike(f"%{user_email}%"))
    if from_date:   filters.append(AuditLog.occurred_at >= from_date)
    if to_date:     filters.append(AuditLog.occurred_at <= to_date)
    if filters:
        q = q.where(and_(*filters))

    logs = (await session.execute(q)).scalars().all()
    return [
        {
            "id":          log.id,
            "occurred_at": log.occurred_at.isoformat(),
            "action":      log.action,
            "entity":      log.entity,
            "entity_id":   log.entity_id,
            "user_id":     log.user_id,
            "user_email":  log.user_email,
            "detail":      log.detail,
            "before":      log.before_json,
            "after":       log.after_json,
        }
        for log in logs
    ]


@router.get("/files", response_model=list[str])
async def list_log_files(_: object = Depends(require_roles(ROLE_ADMIN))):
    """Lista os arquivos .txt de auditoria disponíveis para download."""
    if not _LOG_DIR.exists():
        return []
    return sorted([f.name for f in _LOG_DIR.glob("audit_*.txt")], reverse=True)


@router.get("/files/{filename}")
async def download_log_file(
    filename: str,
    _: object = Depends(require_roles(ROLE_ADMIN)),
):
    """Faz download de um arquivo de log .txt."""
    if not filename.startswith("audit_") or not filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    path = _LOG_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(path, media_type="text/plain", filename=filename)
