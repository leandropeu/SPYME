from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import MonitoringEvent
from ..schemas import MonitoringEventOut
from ..services.auth import get_current_user


router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[MonitoringEventOut])
async def list_events(limit: int = 100, session: AsyncSession = Depends(get_db)):
    events = (
        await session.execute(
            select(MonitoringEvent).order_by(MonitoringEvent.started_at.desc()).limit(limit)
        )
    ).scalars().all()
    return list(events)
