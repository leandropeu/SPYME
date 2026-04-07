"""
app/services/audit.py

Serviço de auditoria — registra toda ação no banco e em arquivo .txt rotativo.
Chamado por qualquer router que modifica dados.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog

logger = logging.getLogger(__name__)

# Diretório de logs em texto — usa SPYGYM_DATA_DIR se definido
_LOG_DIR = Path(os.getenv("SPYGYM_DATA_DIR", Path(__file__).resolve().parents[3] / "backend" / "data")) / "audit_logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log_file() -> Path:
    """Retorna o arquivo de log do mês atual — rotação mensal automática."""
    return _LOG_DIR / f"audit_{datetime.utcnow().strftime('%Y_%m')}.txt"


def _write_txt(entry: str) -> None:
    """Grava linha no arquivo txt de forma síncrona (rápido, sem await)."""
    try:
        with open(_log_file(), "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception as exc:
        logger.warning("Falha ao gravar log em txt: %s", exc)


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    entity_id: int | str | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    detail: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """
    Registra uma ação de auditoria no banco E no arquivo txt.

    Parâmetros:
        action      — verbo: CREATE, UPDATE, DELETE, LOGIN, LOGOUT, ACCESS_PASSWORD, etc.
        entity      — nome da entidade: unit, dvr, camera, user, cloud_account, etc.
        entity_id   — ID do registro afetado (opcional)
        user_id     — ID do usuário que executou a ação
        user_email  — e-mail do usuário (para o txt ficar legível)
        detail      — descrição livre da ação
        before      — estado anterior (para UPDATE/DELETE)
        after       — estado novo (para CREATE/UPDATE)
    """
    import json

    now = datetime.utcnow()
    before_json = json.dumps(before, ensure_ascii=False, default=str) if before else None
    after_json  = json.dumps(after,  ensure_ascii=False, default=str) if after  else None

    # ── Banco ────────────────────────────────────────────────
    log = AuditLog(
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        user_id=user_id,
        user_email=user_email,
        detail=detail,
        before_json=before_json,
        after_json=after_json,
        occurred_at=now,
    )
    session.add(log)
    # Não fazemos commit aqui — o router é responsável pelo commit

    # ── Arquivo TXT ──────────────────────────────────────────
    parts = [
        f"[{now.strftime('%Y-%m-%d %H:%M:%S')} UTC]",
        f"ACTION={action}",
        f"ENTITY={entity}",
    ]
    if entity_id is not None:
        parts.append(f"ID={entity_id}")
    if user_email:
        parts.append(f"USER={user_email}")
    if detail:
        parts.append(f"DETAIL={detail}")
    if before_json:
        parts.append(f"BEFORE={before_json}")
    if after_json:
        parts.append(f"AFTER={after_json}")

    _write_txt(" | ".join(parts))
