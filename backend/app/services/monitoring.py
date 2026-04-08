from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import HEALTHCHECK_CONCURRENCY
from ..db import SessionLocal
from ..models import Camera, DVR, MonitoringEvent, NetworkAsset
from .vendors import fetch_camera_snapshot, fetch_dvr_status, probe_camera_stream


BroadcastHook = Callable[[dict], Awaitable[None]]
_broadcast_hook: BroadcastHook | None = None
_health_check_lock = asyncio.Lock()
logger = logging.getLogger(__name__)


def _is_sqlite_locked(exc: Exception) -> bool:
    return "database is locked" in str(exc).lower()


def set_broadcast_hook(handler: BroadcastHook | None) -> None:
    global _broadcast_hook
    _broadcast_hook = handler


async def _broadcast(payload: dict) -> None:
    if _broadcast_hook:
        await _broadcast_hook(payload)


async def _run_limited(items: list, worker) -> list:
    if not items:
        return []

    semaphore = asyncio.Semaphore(max(1, HEALTHCHECK_CONCURRENCY))

    async def run_item(item):
        async with semaphore:
            return await worker(item)

    return await asyncio.gather(*(run_item(item) for item in items))


async def _resolve_open_events(
    session: AsyncSession,
    *,
    dvr_id: int | None = None,
    camera_id: int | None = None,
    network_asset_id: int | None = None,
    resolved_at: datetime,
) -> None:
    query = select(MonitoringEvent).where(
        MonitoringEvent.is_resolved.is_(False),
        MonitoringEvent.event_type == "offline",
    )
    if dvr_id is not None:
        query = query.where(MonitoringEvent.dvr_id == dvr_id)
    if camera_id is not None:
        query = query.where(MonitoringEvent.camera_id == camera_id)
    if network_asset_id is not None:
        query = query.where(MonitoringEvent.network_asset_id == network_asset_id)

    with session.no_autoflush:
        events = (await session.execute(query)).scalars().all()

    for event in events:
        event.is_resolved = True
        event.resolved_at = resolved_at
        event.duration_seconds = round((resolved_at - event.started_at).total_seconds(), 2)


async def _record_status_change(
    session: AsyncSession,
    *,
    source_type: str,
    title: str,
    message: str,
    unit_id: int | None,
    dvr_id: int | None,
    camera_id: int | None,
    network_asset_id: int | None,
    severity: str,
    event_type: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        MonitoringEvent(
            unit_id=unit_id,
            dvr_id=dvr_id,
            camera_id=camera_id,
            network_asset_id=network_asset_id,
            source_type=source_type,
            title=title,
            message=message,
            severity=severity,
            event_type=event_type,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            started_at=datetime.utcnow(),
            is_resolved=event_type != "offline",
            resolved_at=datetime.utcnow() if event_type != "offline" else None,
        )
    )
    await _broadcast({"type": "event_created", "source_type": source_type, "title": title, "severity": severity})


async def _check_dvrs(session: AsyncSession) -> None:
    now = datetime.utcnow()
    dvrs = (
        await session.execute(
            select(DVR).options(selectinload(DVR.unit), selectinload(DVR.cameras)).where(DVR.is_active.is_(True))
        )
    ).scalars().all()
    results = await _run_limited(dvrs, fetch_dvr_status)

    for dvr, result in zip(dvrs, results):
        await _apply_dvr_result(session, dvr, result, now=now)


async def _apply_dvr_result(
    session: AsyncSession,
    dvr: DVR,
    result: dict,
    *,
    now: datetime,
) -> None:
    new_status = "online" if result["reachable"] else "offline"

    if result["device_info"]:
        dvr.model = dvr.model or result["device_info"].get("model")
        dvr.serial_number = dvr.serial_number or result["device_info"].get("serialNumber")

    if dvr.status != new_status:
        if new_status == "offline":
            await _record_status_change(
                session,
                source_type="dvr",
                title=f"DVR offline: {dvr.name}",
                message=f"O DVR {dvr.name} da unidade {dvr.unit.name} ficou indisponivel.",
                unit_id=dvr.unit_id,
                dvr_id=dvr.id,
                camera_id=None,
                network_asset_id=None,
                severity="critical",
                event_type="offline",
                metadata=result,
            )
        else:
            await _resolve_open_events(session, dvr_id=dvr.id, resolved_at=now)
            await _record_status_change(
                session,
                source_type="dvr",
                title=f"DVR online: {dvr.name}",
                message=f"O DVR {dvr.name} voltou a responder.",
                unit_id=dvr.unit_id,
                dvr_id=dvr.id,
                camera_id=None,
                network_asset_id=None,
                severity="info",
                event_type="online",
                metadata=result,
            )

    dvr.status = new_status
    dvr.last_checked = now
    dvr.last_latency_ms = result.get("latency_ms")
    if new_status == "online":
        dvr.last_seen = now


async def check_single_dvr(session: AsyncSession, dvr: DVR) -> dict:
    result = await fetch_dvr_status(dvr)
    await _apply_dvr_result(session, dvr, result, now=datetime.utcnow())
    return result


async def _check_cameras(session: AsyncSession) -> None:
    now = datetime.utcnow()
    cameras = (
        await session.execute(
            select(Camera).options(selectinload(Camera.unit), selectinload(Camera.dvr)).where(Camera.is_active.is_(True))
        )
    ).scalars().all()

    async def probe_camera(camera: Camera) -> tuple[str, dict]:
        new_status = camera.status
        metadata: dict = {"mode": "derived"}

        if camera.dvr:
            try:
                await fetch_camera_snapshot(camera, camera.dvr)
                new_status = "online"
                metadata = {"mode": "snapshot"}
            except Exception as exc:
                if camera.dvr.status == "online":
                    stream_probe = await probe_camera_stream(camera, camera.dvr)
                    if stream_probe["reachable"]:
                        new_status = "online"
                        metadata = stream_probe | {"mode": "rtsp_probe"}
                    else:
                        new_status = "offline"
                        metadata = {"mode": "snapshot_failed", "detail": str(exc), "stream_probe": stream_probe}
                else:
                    new_status = "offline"
                    metadata = {"mode": "dvr_offline", "detail": str(exc)}
        else:
            new_status = "warning"
            metadata = {"mode": "no_dvr"}

        return new_status, metadata

    results = await _run_limited(cameras, probe_camera)

    for camera, (new_status, metadata) in zip(cameras, results):
        if camera.status != new_status:
            if new_status in {"offline", "warning"}:
                await _record_status_change(
                    session,
                    source_type="camera",
                    title=f"Camera com alerta: {camera.name}",
                    message=f"A camera {camera.name} da unidade {camera.unit.name} requer atencao.",
                    unit_id=camera.unit_id,
                    dvr_id=camera.dvr_id,
                    camera_id=camera.id,
                    network_asset_id=None,
                    severity="warning" if new_status == "warning" else "critical",
                    event_type="offline" if new_status == "offline" else "warning",
                    metadata=metadata,
                )
            else:
                await _resolve_open_events(session, camera_id=camera.id, resolved_at=now)
                await _record_status_change(
                    session,
                    source_type="camera",
                    title=f"Camera online: {camera.name}",
                    message=f"A camera {camera.name} voltou a responder com imagem.",
                    unit_id=camera.unit_id,
                    dvr_id=camera.dvr_id,
                    camera_id=camera.id,
                    network_asset_id=None,
                    severity="info",
                    event_type="online",
                    metadata=metadata,
                )

        camera.status = new_status
        camera.last_checked = now
        if new_status == "online":
            camera.last_seen = now


def _default_port(protocol: str | None) -> int | None:
    protocol = (protocol or "").lower()
    return {
        "http": 80,
        "https": 443,
        "ssh": 22,
        "rdp": 3389,
        "winbox": 8291,
        "rtsp": 554,
        "telnet": 23,
    }.get(protocol)


async def _probe_network_asset(asset: NetworkAsset) -> dict:
    protocol = (asset.protocol or "").lower()
    port = asset.port or _default_port(protocol)
    host = (asset.host or "").strip()
    if not asset.is_active:
        return {"reachable": False, "status": "warning", "detail": "asset_inactive"}
    if not host:
        return {"reachable": False, "status": "warning", "detail": "host_missing"}
    if not port:
        return {"reachable": False, "status": "warning", "detail": "port_missing"}

    started = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=3.5)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {
            "reachable": True,
            "status": "online",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "port": port,
            "protocol": protocol or "tcp",
        }
    except Exception as exc:
        return {
            "reachable": False,
            "status": "offline",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "port": port,
            "protocol": protocol or "tcp",
            "detail": str(exc),
        }


async def _apply_network_asset_result(
    session: AsyncSession,
    asset: NetworkAsset,
    result: dict,
    *,
    now: datetime,
) -> None:
    new_status = result.get("status") or ("online" if result.get("reachable") else "offline")

    if asset.status != new_status:
        if new_status in {"offline", "warning"}:
            await _record_status_change(
                session,
                source_type="network_asset",
                title=f"Ativo de rede com falha: {asset.name}",
                message=f"O ativo {asset.name} da unidade {asset.unit.name} deixou de responder no acesso tecnico.",
                unit_id=asset.unit_id,
                dvr_id=asset.dvr_id,
                camera_id=None,
                network_asset_id=asset.id,
                severity="warning" if new_status == "warning" else "critical",
                event_type="offline" if new_status == "offline" else "warning",
                metadata=result,
            )
        else:
            await _resolve_open_events(session, network_asset_id=asset.id, resolved_at=now)
            await _record_status_change(
                session,
                source_type="network_asset",
                title=f"Ativo de rede online: {asset.name}",
                message=f"O ativo {asset.name} voltou a responder no acesso tecnico.",
                unit_id=asset.unit_id,
                dvr_id=asset.dvr_id,
                camera_id=None,
                network_asset_id=asset.id,
                severity="info",
                event_type="online",
                metadata=result,
            )

    asset.status = new_status
    asset.last_checked = now
    asset.last_latency_ms = result.get("latency_ms")
    if new_status == "online":
        asset.last_seen = now


async def _check_network_assets(session: AsyncSession) -> None:
    now = datetime.utcnow()
    assets = (
        await session.execute(
            select(NetworkAsset)
            .options(selectinload(NetworkAsset.unit), selectinload(NetworkAsset.dvr), selectinload(NetworkAsset.parent_asset))
            .where(NetworkAsset.is_active.is_(True))
        )
    ).scalars().all()
    results = await _run_limited(assets, _probe_network_asset)
    for asset, result in zip(assets, results):
        await _apply_network_asset_result(session, asset, result, now=now)


async def check_single_network_asset(session: AsyncSession, asset: NetworkAsset) -> dict:
    result = await _probe_network_asset(asset)
    await _apply_network_asset_result(session, asset, result, now=datetime.utcnow())
    return result


async def run_health_check(*, skip_if_running: bool = False) -> bool:
    if skip_if_running and _health_check_lock.locked():
        return False

    async with _health_check_lock:
        try:
            async with SessionLocal() as session:
                await _check_dvrs(session)
                await session.commit()

            async with SessionLocal() as session:
                await _check_cameras(session)
                await session.commit()

            async with SessionLocal() as session:
                await _check_network_assets(session)
                await session.commit()

            await _broadcast({"type": "health_check_complete", "checked_at": datetime.utcnow().isoformat()})
            return True
        except OperationalError as exc:
            if skip_if_running and _is_sqlite_locked(exc):
                logger.warning("Health check ignorado: banco SQLite ocupado.")
                return False
            logger.exception("Health check falhou por erro de banco.")
            raise
        except Exception:
            logger.exception("Health check falhou.")
            raise
