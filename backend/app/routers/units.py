from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import Unit
from ..schemas import UnitCreate, UnitOut, UnitUpdate
from ..security import encrypt_secret
from ..services.audit import record as audit
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles


router = APIRouter(prefix="/units", tags=["units"], dependencies=[Depends(get_current_user)])


async def _get_unit_with_relations(session: AsyncSession, unit_id: int) -> Unit | None:
    result = await session.execute(
        select(Unit)
        .where(Unit.id == unit_id)
        .options(selectinload(Unit.dvrs), selectinload(Unit.cameras), selectinload(Unit.network_assets))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def _serialize(unit: Unit) -> UnitOut:
    dvrs = unit.dvrs or []
    cameras = [camera for camera in (unit.cameras or []) if camera.is_active]
    return UnitOut(
        id=unit.id, name=unit.name, code=unit.code, city=unit.city, state=unit.state,
        address=unit.address, manager_name=unit.manager_name, manager_phone=unit.manager_phone,
        network_label=unit.network_label, vpn_type=unit.vpn_type, vpn_host=unit.vpn_host,
        vpn_port=unit.vpn_port, vpn_username=unit.vpn_username, vpn_network_cidr=unit.vpn_network_cidr,
        vpn_adapter_name=unit.vpn_adapter_name, notes=unit.notes, is_active=unit.is_active,
        dvr_count=len(dvrs), camera_count=len(cameras),
        network_asset_count=len([asset for asset in (unit.network_assets or []) if asset.is_active]),
        online_dvrs=sum(1 for d in dvrs if d.status == "online"),
        online_cameras=sum(1 for c in cameras if c.status == "online"),
        has_vpn_password=bool(unit.vpn_password_encrypted),
        has_vpn_psk=bool(unit.vpn_psk_encrypted),
        created_at=unit.created_at, updated_at=unit.updated_at,
    )


@router.get("", response_model=list[UnitOut])
async def list_units(session: AsyncSession = Depends(get_db)):
    units = (await session.execute(
        select(Unit).options(selectinload(Unit.dvrs), selectinload(Unit.cameras), selectinload(Unit.network_assets)).order_by(Unit.name.asc())
    )).scalars().all()
    return [_serialize(u) for u in units]


@router.post("", response_model=UnitOut)
async def create_unit(
    payload: UnitCreate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    if await session.scalar(select(Unit).where(Unit.code == payload.code)):
        raise HTTPException(status_code=409, detail="Ja existe uma unidade com este codigo.")
    data = payload.model_dump(exclude={"vpn_password", "vpn_psk"})
    unit = Unit(
        **data,
        vpn_password_encrypted=encrypt_secret(payload.vpn_password),
        vpn_psk_encrypted=encrypt_secret(payload.vpn_psk),
    )
    session.add(unit)
    await session.flush()
    await audit(session, action="CREATE", entity="unit", entity_id=unit.id,
                user_id=current_user.id, user_email=current_user.email,
                detail=f"Unidade criada: {unit.name}", after=payload.model_dump())
    await session.commit()
    created_unit = await _get_unit_with_relations(session, unit.id)
    return _serialize(created_unit)


@router.put("/{unit_id}", response_model=UnitOut)
async def update_unit(
    unit_id: int, payload: UnitUpdate,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await _get_unit_with_relations(session, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    if await session.scalar(select(Unit).where(Unit.code == payload.code, Unit.id != unit_id)):
        raise HTTPException(status_code=409, detail="Codigo ja utilizado por outra unidade.")
    before = {"name": unit.name, "code": unit.code, "city": unit.city, "is_active": unit.is_active}
    for field, value in payload.model_dump(exclude={"vpn_password", "vpn_psk"}).items():
        setattr(unit, field, value)
    if payload.vpn_password:
        unit.vpn_password_encrypted = encrypt_secret(payload.vpn_password)
    if payload.vpn_psk:
        unit.vpn_psk_encrypted = encrypt_secret(payload.vpn_psk)
    await audit(session, action="UPDATE", entity="unit", entity_id=unit_id,
                user_id=current_user.id, user_email=current_user.email,
                detail=f"Unidade editada: {unit.name}", before=before, after=payload.model_dump())
    await session.commit()
    updated_unit = await _get_unit_with_relations(session, unit_id)
    return _serialize(updated_unit)


@router.delete("/{unit_id}")
async def delete_unit(
    unit_id: int,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    unit = await session.get(Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unidade nao encontrada.")
    await audit(session, action="DELETE", entity="unit", entity_id=unit_id,
                user_id=current_user.id, user_email=current_user.email,
                detail=f"Unidade excluída: {unit.name}",
                before={"name": unit.name, "code": unit.code})
    await session.delete(unit)
    await session.commit()
    return {"message": "Unidade removida com sucesso."}
