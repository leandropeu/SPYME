from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import BackupRecordOut
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles
from ..services.backup import create_backup, list_backups


router = APIRouter(prefix="/backups", tags=["backups"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[BackupRecordOut])
async def get_backups(session: AsyncSession = Depends(get_db)):
    return await list_backups(session)


@router.post("/run", response_model=BackupRecordOut)
async def run_backup(
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    return await create_backup(session)
