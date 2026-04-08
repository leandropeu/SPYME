from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import quote, urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import httpx

from ..db import get_db
from ..models import DVR, NetworkAsset, Unit
from ..schemas import DiscoveredNetworkHost, NetworkAssetCreate, NetworkAssetOut, NetworkAssetUpdate, NetworkAssetWebOut, NetworkDiscoveryOut, NetworkTopologyOut, TopologyEdge, TopologyNode
from ..security import decrypt_secret, encrypt_secret
from ..services.audit import record as audit
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles
from ..services.monitoring import check_single_network_asset
from ..services.network_discovery import DiscoveredHost, discover_network


router = APIRouter(prefix="/network-assets", tags=["network-assets"], dependencies=[Depends(get_current_user)])

DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ssh": 22,
    "rdp": 3389,
    "rtsp": 554,
    "winbox": 8291,
}


def _default_port(protocol: str | None) -> int | None:
    return DEFAULT_PORTS.get((protocol or "").lower())


def _build_connection(asset: NetworkAsset) -> tuple[str | None, str | None]:
    protocol = (asset.protocol or "").lower()
    host = asset.host
    port = asset.port or _default_port(protocol)
    path = asset.path or ""

    if not host:
        return None, None

    if protocol in {"http", "https"}:
        prefix = f"{protocol}://{host}"
        if port and port != _default_port(protocol):
            prefix += f":{port}"
        target = f"{prefix}{path}" if path else prefix
        return "Abrir na web", target

    if protocol == "ssh":
        target = f"ssh {asset.username + '@' if asset.username else ''}{host}"
        if port and port != 22:
            target += f" -p {port}"
        return "Abrir via SSH", target

    if protocol == "rdp":
        target = f"mstsc /v:{host}"
        if port and port != 3389:
            target += f":{port}"
        return "Abrir via RDP", target

    if protocol == "winbox":
        target = f"{host}{f':{port}' if port else ''}"
        return "Abrir via WinBox", target

    if protocol == "rtsp":
        auth = ""
        if asset.username:
            auth = quote(asset.username, safe="")
        prefix = f"rtsp://{auth + '@' if auth else ''}{host}"
        if port:
            prefix += f":{port}"
        target = f"{prefix}{path}" if path else prefix
        return "Abrir via RTSP", target

    target = f"{host}{f':{port}' if port else ''}{path}"
    return "Destino tecnico", target


def _build_asset_http_url(asset: NetworkAsset, path: str | None = None) -> str:
    protocol = (asset.protocol or "http").lower()
    if protocol not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Este ativo nao usa interface HTTP/HTTPS.")

    port = asset.port or _default_port(protocol)
    base = f"{protocol}://{asset.host}"
    if port and port != _default_port(protocol):
        base += f":{port}"

    asset_path = path if path is not None else (asset.path or "/")
    return urljoin(f"{base}/", asset_path.lstrip("/"))


def _validate_asset_target(asset: NetworkAsset, target: str) -> str:
    base = urlparse(_build_asset_http_url(asset))
    parsed = urlparse(target)
    if (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)) != (
        base.scheme,
        base.hostname,
        base.port or (443 if base.scheme == "https" else 80),
    ):
        raise HTTPException(status_code=400, detail="URL de destino invalida para este ativo.")
    return target


def _build_asset_httpx_auth(asset: NetworkAsset) -> tuple[str, str] | None:
    username = (asset.username or "").strip()
    password = decrypt_secret(asset.password_encrypted) or ""
    if not username:
        return None
    return (username, password)


def _rewrite_proxy_html(html_text: str, asset_id: int, token: str | None) -> str:
    token_suffix = f"&token={quote(token, safe='')}" if token else ""

    def build_proxy_path(target_path: str) -> str:
        normalized = target_path if target_path.startswith("/") else f"/{target_path}"
        return f"/api/network-assets/{asset_id}/proxy?path={quote(normalized, safe='/')}{token_suffix}"

    def replace_attr(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote_char = match.group(2)
        target_path = match.group(3)
        return f'{attr}={quote_char}{build_proxy_path(target_path)}{quote_char}'

    def replace_css(match: re.Match[str]) -> str:
        quote_char = match.group(1) or ""
        target_path = match.group(2)
        return f"url({quote_char}{build_proxy_path(target_path)}{quote_char})"

    rewritten = re.sub(r"""(href|src|action)=(["'])/([^"'?#]+(?:\?[^"'#]*)?(?:#[^"']*)?)\2""", replace_attr, html_text)
    rewritten = re.sub(r"""url\((['"]?)/([^)'"]+)\1\)""", replace_css, rewritten)
    return rewritten


def _serialize(asset: NetworkAsset) -> NetworkAssetOut:
    connection_label, connection_target = _build_connection(asset)
    return NetworkAssetOut(
        id=asset.id,
        unit_id=asset.unit_id,
        dvr_id=asset.dvr_id,
        parent_asset_id=asset.parent_asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        vendor=asset.vendor,
        model=asset.model,
        host=asset.host,
        port=asset.port,
        protocol=asset.protocol,
        username=asset.username,
        path=asset.path,
        mac_address=asset.mac_address,
        local_network=asset.local_network,
        notes=asset.notes,
        is_active=asset.is_active,
        status=asset.status,
        unit_name=asset.unit.name if asset.unit else None,
        dvr_name=asset.dvr.name if asset.dvr else None,
        parent_asset_name=asset.parent_asset.name if asset.parent_asset else None,
        has_password=bool(asset.password_encrypted),
        connection_label=connection_label,
        connection_target=connection_target,
        last_seen=asset.last_seen,
        last_checked=asset.last_checked,
        last_latency_ms=asset.last_latency_ms,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


async def _get_asset(session: AsyncSession, asset_id: int) -> NetworkAsset | None:
    result = await session.execute(
        select(NetworkAsset)
        .where(NetworkAsset.id == asset_id)
        .options(
            selectinload(NetworkAsset.unit),
            selectinload(NetworkAsset.dvr),
            selectinload(NetworkAsset.parent_asset),
            selectinload(NetworkAsset.children),
        )
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[NetworkAssetOut])
async def list_network_assets(unit_id: int | None = None, session: AsyncSession = Depends(get_db)):
    query = (
        select(NetworkAsset)
        .options(
            selectinload(NetworkAsset.unit),
            selectinload(NetworkAsset.dvr),
            selectinload(NetworkAsset.parent_asset),
        )
        .order_by(NetworkAsset.name.asc())
    )
    if unit_id:
        query = query.where(NetworkAsset.unit_id == unit_id)
    assets = (await session.execute(query)).scalars().all()
    return [_serialize(asset) for asset in assets]


@router.get("/{asset_id}/web-url", response_model=NetworkAssetWebOut)
async def network_asset_web_url(asset_id: int, session: AsyncSession = Depends(get_db)):
    asset = await _get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")

    url = _build_asset_http_url(asset)
    return NetworkAssetWebOut(
        url=url,
        proxy_url=f"/api/network-assets/{asset.id}/proxy",
        note="Use o proxy para abrir interfaces internas da unidade diretamente pelo SPYGYM.",
    )


@router.get("/topology/{unit_id}", response_model=NetworkTopologyOut)
async def get_network_topology(unit_id: int, session: AsyncSession = Depends(get_db)):
    unit = await session.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")

    assets = (
        await session.execute(
            select(NetworkAsset)
            .where(NetworkAsset.unit_id == unit_id, NetworkAsset.is_active.is_(True))
            .options(selectinload(NetworkAsset.unit), selectinload(NetworkAsset.parent_asset), selectinload(NetworkAsset.dvr))
            .order_by(NetworkAsset.name.asc())
        )
    ).scalars().all()

    nodes: list[TopologyNode] = []
    edges: list[TopologyEdge] = []

    for asset in assets:
        connection_label, connection_target = _build_connection(asset)
        node_id = f"asset-{asset.id}"
        parent_id = f"asset-{asset.parent_asset_id}" if asset.parent_asset_id else None
        nodes.append(
            TopologyNode(
                id=node_id,
                entity_id=asset.id,
                label=asset.name,
                asset_type=asset.asset_type,
                status=asset.status,
                parent_id=parent_id,
                host=f"{asset.host}{f':{asset.port}' if asset.port else ''}",
                unit_name=unit.name,
                connection_label=connection_label,
                connection_target=connection_target,
            )
        )
        if parent_id:
            edges.append(TopologyEdge(source_id=parent_id, target_id=node_id, label="uplink"))

    return NetworkTopologyOut(
        unit_id=unit.id,
        unit_name=unit.name,
        vpn_type=unit.vpn_type,
        vpn_host=unit.vpn_host,
        vpn_port=unit.vpn_port,
        vpn_network_cidr=unit.vpn_network_cidr,
        nodes=nodes,
        edges=edges,
    )


@router.get("/{asset_id}/proxy")
async def network_asset_web_proxy(
    request: Request,
    asset_id: int,
    path: str = "/",
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await _get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")

    target = _validate_asset_target(asset, _build_asset_http_url(asset, path))
    auth = _build_asset_httpx_auth(asset)

    try:
        async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as client:
            resp = await client.get(target, auth=auth)

        headers = dict(resp.headers)
        for header in (
            "x-frame-options",
            "content-security-policy",
            "content-length",
            "content-encoding",
            "x-content-type-options",
        ):
            headers.pop(header, None)
            headers.pop(header.title(), None)

        payload = resp.content
        media_type = resp.headers.get("content-type", "text/html")
        if "text/html" in media_type:
            token = request.query_params.get("token")
            encoding = resp.encoding or "utf-8"
            html_text = resp.content.decode(encoding, errors="ignore")
            payload = _rewrite_proxy_html(html_text, asset.id, token).encode(encoding)

        return StreamingResponse(
            iter([payload]),
            status_code=resp.status_code,
            media_type=media_type,
            headers=headers,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Ativo inacessivel. Verifique host, porta e VPN.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar ativo: {exc}")


def _guess_parent_asset_id(discovered: DiscoveredHost, existing_by_host: dict[str, NetworkAsset], created_by_host: dict[str, NetworkAsset]) -> int | None:
    if discovered.asset_type == "mikrotik":
        return None

    preferred_root = existing_by_host.get("10.0.7.1") or created_by_host.get("10.0.7.1")
    if preferred_root and preferred_root.host != discovered.host:
        return preferred_root.id

    for pool in (created_by_host, existing_by_host):
        for candidate in pool.values():
            if candidate.host == discovered.host:
                continue
            if candidate.asset_type == "mikrotik":
                return candidate.id
    return None


@router.post("/discover/{unit_id}", response_model=NetworkDiscoveryOut)
async def discover_network_assets(
    unit_id: int,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if not unit.vpn_network_cidr:
        raise HTTPException(status_code=400, detail="A unidade nao possui rede VPN/CIDR cadastrada para descoberta.")

    discovered_hosts, scanner = await discover_network(unit.vpn_network_cidr)
    now = datetime.utcnow()

    existing_assets = (
        await session.execute(
            select(NetworkAsset)
            .where(NetworkAsset.unit_id == unit_id)
            .options(selectinload(NetworkAsset.parent_asset), selectinload(NetworkAsset.dvr), selectinload(NetworkAsset.unit))
        )
    ).scalars().all()
    existing_by_host = {asset.host: asset for asset in existing_assets if asset.host}
    created_by_host: dict[str, NetworkAsset] = {}

    dvrs = (await session.execute(select(DVR).where(DVR.unit_id == unit_id))).scalars().all()
    dvr_by_host = {dvr.host: dvr for dvr in dvrs if dvr.host}

    created_count = 0
    updated_count = 0
    payload_hosts: list[DiscoveredNetworkHost] = []

    for discovered in discovered_hosts:
        asset = existing_by_host.get(discovered.host)
        if asset is None:
            asset = NetworkAsset(
                unit_id=unit_id,
                dvr_id=dvr_by_host.get(discovered.host).id if discovered.host in dvr_by_host else None,
                parent_asset_id=None,
                name=discovered.notes.split(".")[0],
                asset_type=discovered.asset_type,
                vendor=discovered.vendor,
                model=discovered.model,
                host=discovered.host,
                port=discovered.port,
                protocol=discovered.protocol,
                local_network=unit.vpn_network_cidr,
                notes=discovered.notes,
                is_active=True,
                status="online",
                last_seen=now,
                last_checked=now,
            )
            session.add(asset)
            await session.flush()
            created_by_host[asset.host] = asset
            existing_by_host[asset.host] = asset
            created_count += 1
        else:
            asset.name = asset.name or discovered.notes.split(".")[0]
            asset.asset_type = discovered.asset_type or asset.asset_type
            asset.vendor = discovered.vendor or asset.vendor
            asset.model = discovered.model or asset.model
            asset.port = discovered.port or asset.port
            asset.protocol = discovered.protocol or asset.protocol
            asset.local_network = asset.local_network or unit.vpn_network_cidr
            asset.status = "online"
            asset.last_seen = now
            asset.last_checked = now
            asset.notes = discovered.notes
            if not asset.dvr_id and discovered.host in dvr_by_host:
                asset.dvr_id = dvr_by_host[discovered.host].id
            updated_count += 1

    for discovered in discovered_hosts:
        asset = existing_by_host[discovered.host]
        parent_asset_id = _guess_parent_asset_id(discovered, existing_by_host, created_by_host)
        if parent_asset_id and parent_asset_id != asset.id:
            asset.parent_asset_id = parent_asset_id
        elif discovered.asset_type == "mikrotik":
            asset.parent_asset_id = None

        payload_hosts.append(
            DiscoveredNetworkHost(
                host=discovered.host,
                name=asset.name,
                asset_type=asset.asset_type,
                vendor=asset.vendor,
                model=asset.model,
                protocol=asset.protocol,
                port=asset.port,
                open_ports=discovered.open_ports,
                notes=asset.notes,
                matched_asset_id=asset.id,
            )
        )

    await audit(
        session,
        action="DISCOVER",
        entity="network_asset",
        entity_id=unit_id,
        user_id=current_user.id,
        user_email=current_user.email,
        detail=f"Descoberta de ativos executada na unidade {unit.name}: {len(discovered_hosts)} hosts.",
        after={
            "unit_id": unit_id,
            "network_cidr": unit.vpn_network_cidr,
            "scanner": scanner,
            "discovered_count": len(discovered_hosts),
            "created_count": created_count,
            "updated_count": updated_count,
        },
    )
    await session.commit()

    return NetworkDiscoveryOut(
        unit_id=unit.id,
        unit_name=unit.name,
        network_cidr=unit.vpn_network_cidr,
        scanner=scanner,
        discovered_count=len(discovered_hosts),
        created_count=created_count,
        updated_count=updated_count,
        hosts=payload_hosts,
    )


@router.post("", response_model=NetworkAssetOut)
async def create_network_asset(
    payload: NetworkAssetCreate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr or dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="DVR vinculado invalido para esta unidade.")
    if payload.parent_asset_id:
        parent = await session.get(NetworkAsset, payload.parent_asset_id)
        if not parent or parent.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="Ativo pai invalido para esta unidade.")

    asset = NetworkAsset(
        **payload.model_dump(exclude={"password"}),
        password_encrypted=encrypt_secret(payload.password),
    )
    session.add(asset)
    await session.flush()
    await audit(
        session,
        action="CREATE",
        entity="network_asset",
        entity_id=asset.id,
        user_id=current_user.id,
        user_email=current_user.email,
        detail=f"Ativo de rede criado: {asset.name}",
        after=payload.model_dump(),
    )
    await session.commit()
    created = await _get_asset(session, asset.id)
    return _serialize(created)


@router.put("/{asset_id}", response_model=NetworkAssetOut)
async def update_network_asset(
    asset_id: int,
    payload: NetworkAssetUpdate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await _get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")
    if payload.parent_asset_id == asset_id:
        raise HTTPException(status_code=400, detail="Um ativo nao pode apontar para ele mesmo.")
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr or dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="DVR vinculado invalido para esta unidade.")
    if payload.parent_asset_id:
        parent = await session.get(NetworkAsset, payload.parent_asset_id)
        if not parent or parent.unit_id != payload.unit_id:
            raise HTTPException(status_code=400, detail="Ativo pai invalido para esta unidade.")

    before = {
        "name": asset.name,
        "host": asset.host,
        "protocol": asset.protocol,
        "parent_asset_id": asset.parent_asset_id,
        "status": asset.status,
    }
    for field, value in payload.model_dump(exclude={"password"}).items():
        setattr(asset, field, value)
    if payload.password:
        asset.password_encrypted = encrypt_secret(payload.password)

    await audit(
        session,
        action="UPDATE",
        entity="network_asset",
        entity_id=asset.id,
        user_id=current_user.id,
        user_email=current_user.email,
        detail=f"Ativo de rede editado: {asset.name}",
        before=before,
        after=payload.model_dump(),
    )
    await session.commit()
    updated = await _get_asset(session, asset.id)
    return _serialize(updated)


@router.delete("/{asset_id}")
async def delete_network_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await session.get(NetworkAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")
    await audit(
        session,
        action="DELETE",
        entity="network_asset",
        entity_id=asset.id,
        user_id=current_user.id,
        user_email=current_user.email,
        detail=f"Ativo de rede removido: {asset.name}",
        before={"name": asset.name, "host": asset.host},
    )
    await session.delete(asset)
    await session.commit()
    return {"message": "Ativo de rede removido com sucesso."}


@router.post("/{asset_id}/check")
async def check_network_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await _get_asset(session, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")
    result = await check_single_network_asset(session, asset)
    await session.commit()
    refreshed = await _get_asset(session, asset.id)
    return {"message": "Verificacao executada.", "status": refreshed.status, "detail": result}
