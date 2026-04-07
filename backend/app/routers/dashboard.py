from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import BackupRecord, Camera, DVR, MonitoringEvent, Unit
from ..schemas import BackupRecordOut, DashboardOverview, MonitoringEventOut, UnitOut
from ..services.auth import get_current_user
from .units import _serialize as serialize_unit


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(session: AsyncSession = Depends(get_db)):
    units = (
        await session.execute(
            select(Unit)
            .options(selectinload(Unit.dvrs), selectinload(Unit.cameras))
            .order_by(Unit.name.asc())
        )
    ).scalars().all()

    critical_events = (
        await session.execute(
            select(MonitoringEvent)
            .where(MonitoringEvent.is_resolved.is_(False))
            .order_by(MonitoringEvent.started_at.desc())
            .limit(8)
        )
    ).scalars().all()

    backups = (
        await session.execute(
            select(BackupRecord).order_by(BackupRecord.started_at.desc()).limit(5)
        )
    ).scalars().all()

    totals = {
        "units":           await session.scalar(select(func.count(Unit.id))) or 0,
        "dvrs":            await session.scalar(select(func.count(DVR.id))) or 0,
        "cameras":         await session.scalar(select(func.count(Camera.id)).where(Camera.is_active.is_(True))) or 0,
        "online_dvrs":     await session.scalar(select(func.count(DVR.id)).where(DVR.status == "online")) or 0,
        "online_cameras":  await session.scalar(select(func.count(Camera.id)).where(Camera.is_active.is_(True), Camera.status == "online")) or 0,
        "warning_cameras": await session.scalar(select(func.count(Camera.id)).where(Camera.is_active.is_(True), Camera.status == "warning")) or 0,
        "critical_events": len(critical_events),
    }

    return DashboardOverview(
        totals=totals,
        # serialize_unit já retorna UnitOut — não precisa de model_validate
        critical_events=[MonitoringEventOut.model_validate(item) for item in critical_events],
        units=[serialize_unit(unit) for unit in units],
        latest_backups=[BackupRecordOut.model_validate(item) for item in backups],
    )
