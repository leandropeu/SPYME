from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import CloudAccount, DVR
from ..schemas import CloudAccountCreate, CloudAccountOut, CloudAccountUpdate
from ..security import encrypt_secret, decrypt_secret
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles

router = APIRouter(
    prefix="/cloud-accounts",
    tags=["cloud-accounts"],
    dependencies=[Depends(get_current_user)],
)

VALID_VENDORS = ("hikvision", "intelbras")


def _serialize(account: CloudAccount) -> CloudAccountOut:
    return CloudAccountOut(
        id=account.id,
        name=account.name,
        vendor=account.vendor,
        email=account.email,
        notes=account.notes,
        has_password=bool(account.password_enc),
        dvr_count=len(account.dvrs or []),
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


# ── LIST ─────────────────────────────────────────────────────

@router.get("", response_model=list[CloudAccountOut])
async def list_cloud_accounts(
    vendor: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    query = (
        select(CloudAccount)
        .options(selectinload(CloudAccount.dvrs))
        .order_by(CloudAccount.name.asc())
    )
    if vendor:
        query = query.where(CloudAccount.vendor == vendor.lower())
    accounts = (await session.execute(query)).scalars().all()
    return [_serialize(a) for a in accounts]


# ── GET ──────────────────────────────────────────────────────

@router.get("/{account_id}", response_model=CloudAccountOut)
async def get_cloud_account(
    account_id: int,
    session: AsyncSession = Depends(get_db),
):
    account = await session.get(CloudAccount, account_id, options=[selectinload(CloudAccount.dvrs)])
    if not account:
        raise HTTPException(status_code=404, detail="Conta cloud não encontrada.")
    return _serialize(account)


# ── CREATE ───────────────────────────────────────────────────

@router.post("", response_model=CloudAccountOut)
async def create_cloud_account(
    payload: CloudAccountCreate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    vendor = payload.vendor.lower()
    if vendor not in VALID_VENDORS:
        raise HTTPException(status_code=422, detail=f"vendor deve ser um de: {', '.join(VALID_VENDORS)}.")

    account = CloudAccount(
        name=payload.name.strip(),
        vendor=vendor,
        email=payload.email.strip(),
        password_enc=encrypt_secret(payload.password),
        notes=payload.notes,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account, attribute_names=["dvrs"])
    return _serialize(account)


# ── UPDATE ───────────────────────────────────────────────────

@router.put("/{account_id}", response_model=CloudAccountOut)
async def update_cloud_account(
    account_id: int,
    payload: CloudAccountUpdate,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    account = await session.get(CloudAccount, account_id, options=[selectinload(CloudAccount.dvrs)])
    if not account:
        raise HTTPException(status_code=404, detail="Conta cloud não encontrada.")

    if payload.name     is not None: account.name  = payload.name.strip()
    if payload.email    is not None: account.email = payload.email.strip()
    if payload.notes    is not None: account.notes = payload.notes
    if payload.vendor   is not None:
        vendor = payload.vendor.lower()
        if vendor not in VALID_VENDORS:
            raise HTTPException(status_code=422, detail=f"vendor deve ser um de: {', '.join(VALID_VENDORS)}.")
        account.vendor = vendor
    if payload.password is not None:
        account.password_enc = encrypt_secret(payload.password)

    await session.commit()
    await session.refresh(account, attribute_names=["dvrs"])
    return _serialize(account)


# ── DELETE ───────────────────────────────────────────────────

@router.delete("/{account_id}")
async def delete_cloud_account(
    account_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    account = await session.get(CloudAccount, account_id, options=[selectinload(CloudAccount.dvrs)])
    if not account:
        raise HTTPException(status_code=404, detail="Conta cloud não encontrada.")

    if account.dvrs:
        raise HTTPException(
            status_code=409,
            detail=f"Conta vinculada a {len(account.dvrs)} DVR(s). Desvincule antes de excluir.",
        )

    await session.delete(account)
    await session.commit()
    return {"message": "Conta cloud removida com sucesso."}


# ── DVRs DA CONTA ─────────────────────────────────────────────

@router.get("/{account_id}/dvrs", response_model=list[dict])
async def list_dvrs_of_account(
    account_id: int,
    session: AsyncSession = Depends(get_db),
):
    account = await session.get(CloudAccount, account_id, options=[selectinload(CloudAccount.dvrs)])
    if not account:
        raise HTTPException(status_code=404, detail="Conta cloud não encontrada.")
    return [
        {
            "id":            dvr.id,
            "name":          dvr.name,
            "unit_id":       dvr.unit_id,
            "device_serial": dvr.device_serial,
            "status":        dvr.status,
        }
        for dvr in account.dvrs
    ]


# ── REVEAL PASSWORD (apenas admin) ───────────────────────────

@router.get("/{account_id}/reveal-password")
async def reveal_password(
    account_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN)),
):
    account = await session.get(CloudAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Conta cloud não encontrada.")
    return {"password": decrypt_secret(account.password_enc)}
