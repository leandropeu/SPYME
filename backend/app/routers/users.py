from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..schemas import UserCreate, UserOut, UserUpdate
from ..security import hash_password
from ..services.auth import ROLE_ADMIN, get_current_user, normalize_email, require_roles, validate_role


router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_roles(ROLE_ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    users = (await session.execute(select(User).order_by(User.full_name.asc()))).scalars().all()
    return [UserOut.model_validate(user) for user in users]


@router.post("", response_model=UserOut)
async def create_user_route(
    payload: UserCreate,
    _: User = Depends(require_roles(ROLE_ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    existing = await session.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if existing:
        raise HTTPException(status_code=409, detail="Ja existe um usuario com este e-mail.")

    user = User(
        full_name=payload.full_name.strip(),
        email=normalize_email(payload.email),
        role=validate_role(payload.role),
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.put("/{user_id}", response_model=UserOut)
async def update_user_route(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")

    email = normalize_email(payload.email)
    existing = await session.scalar(select(User).where(User.email == email, User.id != user_id))
    if existing:
        raise HTTPException(status_code=409, detail="Ja existe um usuario com este e-mail.")

    user.full_name = payload.full_name.strip()
    user.email = email
    user.role = validate_role(payload.role)
    user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)

    if current_user.id == user.id and not user.is_active:
        raise HTTPException(status_code=400, detail="Voce nao pode desativar sua propria conta.")

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}")
async def delete_user_route(
    user_id: int,
    current_user: User = Depends(require_roles(ROLE_ADMIN)),
    session: AsyncSession = Depends(get_db),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    if current_user.id == user.id:
        raise HTTPException(status_code=400, detail="Voce nao pode excluir sua propria conta.")
    await session.delete(user)
    await session.commit()
    return {"message": "Usuario removido com sucesso."}
