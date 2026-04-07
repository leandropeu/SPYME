"""
app/core/crypto.py

Criptografia simétrica Fernet derivada do SPYGYM_SECRET_SEED.
Reutiliza a mesma semente já definida no .env, sem precisar de nova variável.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_fernet_instance: Fernet | None = None

SALT = b"spygym_cloud_accounts_v1"  # salt fixo — não é segredo, só garante domínio isolado


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    seed = os.getenv("SPYGYM_SECRET_SEED", "")
    if not seed:
        raise RuntimeError(
            "SPYGYM_SECRET_SEED não definida no .env. "
            "Adicione uma string secreta forte para habilitar criptografia de senhas cloud."
        )

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=260_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(seed.encode()))
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_password(plain: str) -> str:
    """Recebe senha em texto puro, retorna string criptografada segura para o banco."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_password(token: str) -> str:
    """Recebe string criptografada do banco, retorna senha em texto puro."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Falha ao descriptografar senha cloud. "
            "Verifique se SPYGYM_SECRET_SEED não foi alterada."
        ) from exc
