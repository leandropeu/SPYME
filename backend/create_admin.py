import asyncio
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.services.auth import create_user, ROLE_ADMIN

async def main():
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.email == "admin@admin.com")
        )

        if existing:
            print("Admin já existe:", existing.email)
            return

        user = await create_user(
            session,
            full_name="Administrador",
            email="admin@admin.com",
            password="123456",
            role=ROLE_ADMIN,
            is_active=True,
        )

        print("Admin criado com sucesso:", user.email)

asyncio.run(main())
