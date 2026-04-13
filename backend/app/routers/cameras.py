from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import Camera, DVR, Unit
from ..schemas import CameraCreate, CameraOut, CameraUpdate
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles, resolve_user_by_token
from ..services.vendors import build_snapshot_placeholder, build_stream_reference, fetch_camera_snapshot, resolve_snapshot_url


router = APIRouter(prefix="/cameras", tags=["cameras"])
bearer_scheme = HTTPBearer(auto_error=False)


def _serialize(camera: Camera) -> CameraOut:
    return CameraOut(
        id=camera.id,
        unit_id=camera.unit_id,
        dvr_id=camera.dvr_id,
        name=camera.name,
        vendor=camera.vendor,
        model=camera.model,
        channel_number=camera.channel_number,
        location=camera.location,
        resolution=camera.resolution,
        snapshot_path=camera.snapshot_path,
        snapshot_url=camera.snapshot_url,
        stream_path=camera.stream_path,
        stream_url=camera.stream_url,
        notes=camera.notes,
        is_active=camera.is_active,
        status=camera.status,
        unit_name=camera.unit.name if camera.unit else None,
        dvr_name=camera.dvr.name if camera.dvr else None,
        last_seen=camera.last_seen,
        last_checked=camera.last_checked,
        snapshot_endpoint=f"/api/cameras/{camera.id}/snapshot",
        preview_ready=bool(resolve_snapshot_url(camera, camera.dvr)),
        stream_reference=build_stream_reference(camera, camera.dvr),
        created_at=camera.created_at,
        updated_at=camera.updated_at,
    )


@router.get("", response_model=list[CameraOut])
async def list_cameras(
    unit_id: int | None = None,
    dvr_id: int | None = None,
    _: object = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(Camera)
        .options(selectinload(Camera.unit), selectinload(Camera.dvr))
        .where(Camera.is_active.is_(True))
        .order_by(Camera.name.asc())
    )
    if unit_id:
        query = query.where(Camera.unit_id == unit_id)
    if dvr_id:
        query = query.where(Camera.dvr_id == dvr_id)

    cameras = (await session.execute(query)).scalars().all()
    return [_serialize(item) for item in cameras]


@router.post("", response_model=CameraOut)
async def create_camera(
    payload: CameraCreate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    dvr = None
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr:
            raise HTTPException(status_code=404, detail="DVR nao encontrado.")
        if dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="O DVR selecionado nao pertence a esta unidade.")
        duplicate = await session.scalar(
            select(Camera).where(
                Camera.dvr_id == payload.dvr_id,
                Camera.channel_number == payload.channel_number,
                Camera.is_active.is_(True),
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Ja existe uma camera ativa neste canal para o DVR selecionado.")

    camera = Camera(**payload.model_dump())
    session.add(camera)
    await session.commit()
    await session.refresh(camera, attribute_names=["unit", "dvr"])
    return _serialize(camera)


@router.put("/{camera_id}", response_model=CameraOut)
async def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    camera = await session.get(Camera, camera_id, options=[selectinload(Camera.unit), selectinload(Camera.dvr)])
    if not camera:
        raise HTTPException(status_code=404, detail="Camera nao encontrada.")
    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr:
            raise HTTPException(status_code=404, detail="DVR nao encontrado.")
        if dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="O DVR selecionado nao pertence a esta unidade.")
        duplicate = await session.scalar(
            select(Camera).where(
                Camera.dvr_id == payload.dvr_id,
                Camera.channel_number == payload.channel_number,
                Camera.id != camera_id,
                Camera.is_active.is_(True),
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Ja existe uma camera ativa neste canal para o DVR selecionado.")

    for field, value in payload.model_dump().items():
        setattr(camera, field, value)

    await session.commit()
    await session.refresh(camera)
    return _serialize(camera)


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    camera = await session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera nao encontrada.")
    await session.delete(camera)
    await session.commit()
    return {"message": "Camera removida com sucesso."}


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: int,
    token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
):
    raw_token = token or (credentials.credentials if credentials else None)
    await resolve_user_by_token(session, raw_token)
    camera = await session.get(Camera, camera_id, options=[selectinload(Camera.dvr)])
    if not camera:
        raise HTTPException(status_code=404, detail="Camera nao encontrada.")

    try:
        content, content_type = await fetch_camera_snapshot(camera, camera.dvr)
    except Exception as exc:
        content, content_type = build_snapshot_placeholder(camera, camera.dvr, str(exc))

    return StreamingResponse(iter([content]), media_type=content_type)
