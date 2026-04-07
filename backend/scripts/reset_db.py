"""
scripts/reset_db.py

Apaga TODOS os dados do banco SPYGYM e recria apenas o usuário admin.

Uso:
    cd C:\\Users\\Admin\\X\\SPYGYM\\backend
    .\.venv\Scripts\activate
    py -3 scripts/reset_db.py

    # Sem prompt:
    py -3 scripts/reset_db.py --yes
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, text

from app.db import SessionLocal, init_db
from app.models import (
    AuthToken,
    BackupRecord,
    Camera,
    CloudAccount,
    DVR,
    MonitoringEvent,
    Unit,
    User,
)
from app.services.seed import ensure_admin_user


TABLES_TO_CLEAR = [
    AuthToken,
    MonitoringEvent,
    Camera,
    DVR,
    CloudAccount,
    Unit,
    BackupRecord,
    User,
]


async def reset(confirmed: bool = False) -> None:
    if not confirmed:
        print("\n⚠️  ATENÇÃO: Este script apaga TODOS os dados do banco SPYGYM.")
        print("   Apenas o usuário admin será recriado.")
        resposta = input("\n   Digite 'CONFIRMAR' para continuar: ").strip()
        if resposta != "CONFIRMAR":
            print("   Operação cancelada.")
            return

    print("\n🔄 Inicializando banco e tabelas...")
    await init_db()

    async with SessionLocal() as session:
        print("🗑️  Apagando dados...")

        for model in TABLES_TO_CLEAR:
            result = await session.execute(delete(model))
            print(f"   {model.__tablename__}: {result.rowcount} registros removidos")

        # sqlite_sequence só existe após o primeiro INSERT — ignorar se ausente
        for model in TABLES_TO_CLEAR:
            try:
                await session.execute(
                    text(f"DELETE FROM sqlite_sequence WHERE name='{model.__tablename__}'")
                )
            except Exception:
                pass

        await session.commit()
        print("\n✅ Banco limpo.")

        print("👤 Recriando usuário admin...")
        await ensure_admin_user(session)
        print("   Admin criado com sucesso.")

    print("\n🎉 Banco zerado e pronto para dados reais.")
    print("   Confirme SPYGYM_AUTO_SEED_DEMO=false no seu .env\n")


if __name__ == "__main__":
    asyncio.run(reset(confirmed="--yes" in sys.argv))
