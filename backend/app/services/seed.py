from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import ADMIN_EMAIL, ADMIN_NAME, ADMIN_PASSWORD
from ..models import User
from .auth import ROLE_ADMIN, create_user, normalize_email


async def ensure_admin_user(session: AsyncSession) -> None:
    """Garante que o usuário admin existe. Nunca recria se já existir."""
    admin = await session.scalar(select(User).where(User.email == normalize_email(ADMIN_EMAIL)))
    if admin:
        return

    await create_user(
        session,
        full_name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        password=ADMIN_PASSWORD,
        role=ROLE_ADMIN,
        is_active=True,
    )


async def seed_demo_data(session: AsyncSession) -> None:
    """
    Ponto de entrada chamado pelo lifespan do FastAPI.
    Dados fictícios foram REMOVIDOS — apenas o admin é garantido.
    Para reativar o seed de demonstração, implemente aqui com AUTO_SEED_DEMO=true no .env.
    """
    await ensure_admin_user(session)
