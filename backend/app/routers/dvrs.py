from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import Camera, DVR, Unit
from ..schemas import CloudAccountSummary, DVRCreate, DVROut, DVRUpdate
from ..security import encrypt_secret
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles
from ..services.dvr_remote import get_channels
from ..services.monitoring import check_single_dvr
from ..services.vendors import build_default_camera_payload, probe_camera_stream


router = APIRouter(prefix="/dvrs", tags=["dvrs"], dependencies=[Depends(get_current_user)])


def _serialize(dvr: DVR) -> DVROut:
    active_cameras = [camera for camera in (dvr.cameras or []) if camera.is_active]
    notes_text = (dvr.notes or "").lower()
    auto_discovered = "descoberto automaticamente" in notes_text
    pending_credentials = auto_discovered and not bool(dvr.password_encrypted)
    cloud = None
    if dvr.cloud_account:
        cloud = CloudAccountSummary(
            id=dvr.cloud_account.id,
            name=dvr.cloud_account.name,
            vendor=dvr.cloud_account.vendor,
            email=dvr.cloud_account.email,
        )

    return DVROut(
        id=dvr.id,
        unit_id=dvr.unit_id,
        name=dvr.name,
        vendor=dvr.vendor,
        model=dvr.model,
        serial_number=dvr.serial_number,
        host=dvr.host,
        port=dvr.port,
        protocol=dvr.protocol,
        username=dvr.username,
        owner_username=dvr.owner_username,
        channel_count=dvr.channel_count,
        api_status_path=dvr.api_status_path,
        device_info_path=dvr.device_info_path,
        notes=dvr.notes,
        is_active=dvr.is_active,
        status=dvr.status,
        last_seen=dvr.last_seen,
        last_checked=dvr.last_checked,
        last_latency_ms=dvr.last_latency_ms,
        has_password=bool(dvr.password_encrypted),
        has_owner_password=bool(dvr.owner_password_encrypted),
        auto_discovered=auto_discovered,
        pending_credentials=pending_credentials,
        unit_name=dvr.unit.name if dvr.unit else None,
        camera_count=len(active_cameras),
        cloud_account_id=dvr.cloud_account_id,
        device_serial=dvr.device_serial,
        cloud_account=cloud,
        created_at=dvr.created_at,
        updated_at=dvr.updated_at,
    )


@router.get("", response_model=list[DVROut])
async def list_dvrs(unit_id: int | None = None, session: AsyncSession = Depends(get_db)):
    query = (
        select(DVR)
        .options(
            selectinload(DVR.unit),
            selectinload(DVR.cameras),
            selectinload(DVR.cloud_account),
        )
        .order_by(DVR.name.asc())
    )
    if unit_id:
        query = query.where(DVR.unit_id == unit_id)
    dvrs = (await session.execute(query)).scalars().all()
    return [_serialize(item) for item in dvrs]


@router.post("", response_model=DVROut)
async def create_dvr(
    payload: DVRCreate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    owner_username = (payload.owner_username or "").strip() or None

    dvr = DVR(
        **payload.model_dump(exclude={"password", "owner_password", "owner_username"}),
        owner_username=owner_username,
        password_encrypted=encrypt_secret(payload.password),
        owner_password_encrypted=encrypt_secret(payload.owner_password),
    )
    session.add(dvr)
    await session.commit()
    await session.refresh(dvr, attribute_names=["unit", "cameras", "cloud_account"])
    return _serialize(dvr)


@router.put("/{dvr_id}", response_model=DVROut)
async def update_dvr(
    dvr_id: int,
    payload: DVRUpdate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await session.get(
        DVR, dvr_id,
        options=[
            selectinload(DVR.unit),
            selectinload(DVR.cameras),
            selectinload(DVR.cloud_account),
        ],
    )
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR nao encontrado.")
    owner_username = (payload.owner_username or "").strip()
    owner_password = (payload.owner_password or "").strip()
    if owner_password and not owner_username:
        raise HTTPException(status_code=400, detail="Preencha o login proprietario para salvar a senha proprietaria.")
    if owner_username and owner_username != (dvr.owner_username or "") and not owner_password and not dvr.owner_password_encrypted:
        raise HTTPException(status_code=400, detail="Ao definir um novo login proprietario, informe tambem a senha proprietaria.")

    for field, value in payload.model_dump(exclude={"password", "owner_password", "owner_username"}).items():
        setattr(dvr, field, value)
    dvr.owner_username = owner_username or None
    if payload.password:
        dvr.password_encrypted = encrypt_secret(payload.password)
    if owner_password:
        dvr.owner_password_encrypted = encrypt_secret(owner_password)
    elif not owner_username:
        dvr.owner_password_encrypted = None

    await session.commit()
    await session.refresh(dvr, attribute_names=["unit", "cameras", "cloud_account"])
    return _serialize(dvr)


@router.delete("/{dvr_id}")
async def delete_dvr(
    dvr_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await session.get(DVR, dvr_id)
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR nao encontrado.")
    await session.delete(dvr)
    await session.commit()
    return {"message": "DVR removido com sucesso."}


@router.post("/{dvr_id}/check")
async def check_dvr(
    dvr_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await session.get(
        DVR,
        dvr_id,
        options=[selectinload(DVR.unit), selectinload(DVR.cameras), selectinload(DVR.cloud_account)],
    )
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR nao encontrado.")
    await check_single_dvr(session, dvr)
    await session.commit()
    refreshed = await session.get(
        DVR,
        dvr_id,
        options=[selectinload(DVR.unit), selectinload(DVR.cameras), selectinload(DVR.cloud_account)],
    )
    return {"message": "Verificacao executada.", "status": refreshed.status}


@router.post("/{dvr_id}/sync-cameras")
async def sync_cameras(
    dvr_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await session.get(DVR, dvr_id, options=[selectinload(DVR.cameras)])
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR nao encontrado.")

    existing_by_channel = {camera.channel_number: camera for camera in dvr.cameras}
    remote_channel_map: dict[int, dict] = {}
    channel_names: dict[int, str] = {}
    try:
        remote_channels = await get_channels(dvr)
        for channel in remote_channels:
            try:
                channel_id = int(channel.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if channel_id:
                remote_channel_map[channel_id] = channel
                channel_names[channel_id] = channel.get("name") or f"Camera {channel_id:02d}"
    except Exception:
        remote_channels = []

    created = 0
    reactivated = 0
    deactivated = 0

    for channel in range(1, dvr.channel_count + 1):
        defaults = build_default_camera_payload(dvr, channel)
        remote_channel = remote_channel_map.get(channel) or {}
        display_name = channel_names.get(channel) or defaults["name"]
        stream_path = remote_channel.get("preferred_stream_path") or defaults["stream_path"]
        existing_camera = existing_by_channel.get(channel)
        has_video = remote_channel.get("has_video")

        if has_video is None:
            probe_target = existing_camera or Camera(
                unit_id=dvr.unit_id,
                dvr_id=dvr.id,
                name=display_name,
                vendor=defaults["vendor"],
                channel_number=channel,
                snapshot_path=defaults["snapshot_path"],
                stream_path=stream_path,
                status="unknown",
                is_active=True,
            )
            try:
                stream_probe = await probe_camera_stream(probe_target, dvr)
                channel_reachable = bool(stream_probe.get("reachable"))
            except Exception:
                channel_reachable = False
        else:
            channel_reachable = bool(has_video)

        if channel_reachable:
            if existing_camera:
                if not existing_camera.is_active:
                    existing_camera.is_active = True
                    reactivated += 1
                existing_camera.vendor = existing_camera.vendor or defaults["vendor"]
                existing_camera.snapshot_path = defaults["snapshot_path"]
                existing_camera.stream_path = stream_path
                if not existing_camera.name or existing_camera.name == f"Camera {channel:02d}":
                    existing_camera.name = display_name
            else:
                session.add(
                    Camera(
                        unit_id=dvr.unit_id,
                        dvr_id=dvr.id,
                        name=display_name,
                        vendor=defaults["vendor"],
                        channel_number=defaults["channel_number"],
                        snapshot_path=defaults["snapshot_path"],
                        stream_path=stream_path,
                        status="unknown",
                        is_active=True,
                    )
                )
                created += 1
        elif existing_camera and existing_camera.is_active:
            existing_camera.is_active = False
            existing_camera.status = "offline"
            deactivated += 1

    await session.commit()
    active_total = await session.scalar(
        select(func.count(Camera.id)).where(Camera.dvr_id == dvr.id, Camera.is_active.is_(True))
    ) or 0
    return {
        "message": "Sincronizacao concluida.",
        "created": created,
        "reactivated": reactivated,
        "deactivated": deactivated,
        "active_cameras": max(active_total, 0),
        "capacity": dvr.channel_count,
    }
