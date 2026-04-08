from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Cookie, Depends, HTTPException, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import TOKEN_TTL_HOURS
from ..db import SessionLocal, get_db
from ..models import AuthToken, User
from ..security import generate_api_token, hash_api_token, hash_password, verify_password


ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"
ROLE_OPTIONS = [ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER]

bearer_scheme = HTTPBearer(auto_error=False)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ROLE_OPTIONS:
        raise HTTPException(status_code=422, detail="Perfil invalido.")
    return normalized


async def cleanup_expired_tokens(session: AsyncSession) -> None:
    now = datetime.utcnow()
    expired_tokens = (
        await session.execute(
            select(AuthToken).where(AuthToken.expires_at <= now, AuthToken.revoked_at.is_(None))
        )
    ).scalars().all()
    for token in expired_tokens:
        token.revoked_at = now
    if expired_tokens:
        await session.commit()


async def create_user(
    session: AsyncSession,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str = ROLE_VIEWER,
    is_active: bool = True,
) -> User:
    user = User(
        full_name=full_name.strip(),
        email=normalize_email(email),
        role=validate_role(role),
        password_hash=hash_password(password),
        is_active=is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def issue_token(session: AsyncSession, user: User) -> tuple[str, datetime]:
    await cleanup_expired_tokens(session)
    raw_token = generate_api_token()
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)
    session.add(
        AuthToken(
            user_id=user.id,
            token_hash=hash_api_token(raw_token),
            expires_at=expires_at,
            last_seen_at=datetime.utcnow(),
        )
    )
    user.last_login_at = datetime.utcnow()
    await session.commit()
    return raw_token, expires_at


async def revoke_token(session: AsyncSession, raw_token: str) -> None:
    token_record = await session.scalar(select(AuthToken).where(AuthToken.token_hash == hash_api_token(raw_token)))
    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.utcnow()
        await session.commit()


async def resolve_user_by_token(session: AsyncSession, raw_token: str | None) -> User:
    if not raw_token:
        raise HTTPException(status_code=401, detail="Token nao informado.")

    token_record = await session.scalar(
        select(AuthToken)
        .options(selectinload(AuthToken.user))
        .where(AuthToken.token_hash == hash_api_token(raw_token))
    )
    if not token_record or token_record.revoked_at is not None or token_record.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")

    user = token_record.user
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inativo.")

    token_record.last_seen_at = datetime.utcnow()
    await session.commit()
    return user


async def get_current_user(
    token: str | None = None,
    spygym_token: str | None = Cookie(default=None, alias="spygym_token"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    raw_token = token or spygym_token or (credentials.credentials if credentials else None)
    return await resolve_user_by_token(session, raw_token)


def require_roles(*roles: str):
    allowed = {validate_role(role) for role in roles}

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail="Perfil sem permissao para esta acao.")
        return current_user

    return dependency


async def authenticate_websocket(websocket: WebSocket) -> User:
    raw_token = websocket.query_params.get("token")
    async with SessionLocal() as session:
        return await resolve_user_by_token(session, raw_token)
