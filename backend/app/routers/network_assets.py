from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import DVR, NetworkAsset, Unit
from ..schemas import NetworkAssetCreate, NetworkAssetOut, NetworkAssetUpdate
from ..security import encrypt_secret
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles


router = APIRouter(prefix="/network-assets", tags=["network-assets"], dependencies=[Depends(get_current_user)])


def _build_connection(asset: NetworkAsset) -> tuple[str | None, str | None]:
    protocol = (asset.protocol or "").lower()
    host = asset.host
    if not host:
        return None, None

    if protocol in {"http", "https", "rtsp"}:
        port = f":{asset.port}" if asset.port else ""
        path = asset.path or ""
        if path and not path.startswith("/"):
            path = f"/{path}"
        return "Abrir URL", f"{protocol}://{host}{port}{path}"
    if protocol == "ssh":
        port = f" -p {asset.port}" if asset.port else ""
        target = f"{asset.username}@{host}" if asset.username else host
        return "SSH", f"ssh{port} {target}"
    if protocol == "rdp":
        port = f":{asset.port}" if asset.port else ""
        return "RDP", f"mstsc /v:{host}{port}"
    if protocol == "winbox":
        return "WinBox", host
    return protocol.upper() if protocol else "Conexao", host


def _serialize(asset: NetworkAsset) -> NetworkAssetOut:
    label, target = _build_connection(asset)
    return NetworkAssetOut(
        id=asset.id,
        unit_id=asset.unit_id,
        dvr_id=asset.dvr_id,
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
        unit_name=asset.unit.name if asset.unit else None,
        dvr_name=asset.dvr.name if asset.dvr else None,
        has_password=bool(asset.password_encrypted),
        connection_label=label,
        connection_target=target,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


@router.get("", response_model=list[NetworkAssetOut])
async def list_network_assets(
    unit_id: int | None = None,
    asset_type: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(NetworkAsset)
        .options(selectinload(NetworkAsset.unit), selectinload(NetworkAsset.dvr))
        .order_by(NetworkAsset.name.asc())
    )
    if unit_id:
        query = query.where(NetworkAsset.unit_id == unit_id)
    if asset_type:
        query = query.where(NetworkAsset.asset_type == asset_type)
    assets = (await session.execute(query)).scalars().all()
    return [_serialize(asset) for asset in assets]


@router.post("", response_model=NetworkAssetOut)
async def create_network_asset(
    payload: NetworkAssetCreate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr or dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=422, detail="DVR invalido para a unidade selecionada.")

    asset = NetworkAsset(
        **payload.model_dump(exclude={"password"}),
        password_encrypted=encrypt_secret(payload.password),
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset, attribute_names=["unit", "dvr"])
    return _serialize(asset)


@router.put("/{asset_id}", response_model=NetworkAssetOut)
async def update_network_asset(
    asset_id: int,
    payload: NetworkAssetUpdate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await session.get(
        NetworkAsset,
        asset_id,
        options=[selectinload(NetworkAsset.unit), selectinload(NetworkAsset.dvr)],
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")

    unit = await session.get(Unit, payload.unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if payload.dvr_id:
        dvr = await session.get(DVR, payload.dvr_id)
        if not dvr or dvr.unit_id != payload.unit_id:
            raise HTTPException(status_code=422, detail="DVR invalido para a unidade selecionada.")

    for field, value in payload.model_dump(exclude={"password"}).items():
        setattr(asset, field, value)
    if payload.password:
        asset.password_encrypted = encrypt_secret(payload.password)

    await session.commit()
    await session.refresh(asset, attribute_names=["unit", "dvr"])
    return _serialize(asset)


@router.delete("/{asset_id}")
async def delete_network_asset(
    asset_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    asset = await session.get(NetworkAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Ativo de rede nao encontrado.")
    await session.delete(asset)
    await session.commit()
    return {"message": "Ativo de rede removido com sucesso."}
