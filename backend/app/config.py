from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("SPYGYM_DATA_DIR", BACKEND_DIR / "data"))
BACKUP_DIR = Path(os.getenv("SPYGYM_BACKUP_DIR", DATA_DIR / "backups"))
DB_PATH = Path(os.getenv("SPYGYM_DB_PATH", DATA_DIR / "spygym.db"))

APP_NAME = "SPYGYM"
APP_ENV = os.getenv("SPYGYM_ENV", "development")
APP_HOST = os.getenv("SPYGYM_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("SPYGYM_PORT", "8000"))

HEALTHCHECK_SECONDS = int(os.getenv("SPYGYM_HEALTHCHECK_SECONDS", "60"))
HEALTHCHECK_CONCURRENCY = int(os.getenv("SPYGYM_HEALTHCHECK_CONCURRENCY", "10"))
BACKUP_HOURS = int(os.getenv("SPYGYM_BACKUP_HOURS", "2"))
BACKUP_RETENTION_DAYS = int(os.getenv("SPYGYM_BACKUP_RETENTION_DAYS", "5"))
BACKUP_MAX_FILES = int(os.getenv("SPYGYM_BACKUP_MAX_FILES", str((24 // max(BACKUP_HOURS, 1)) * BACKUP_RETENTION_DAYS)))

AUTO_SEED_DEMO = os.getenv("SPYGYM_AUTO_SEED_DEMO", "true").lower() == "true"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "SPYGYM_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if origin.strip()
]
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("SPYGYM_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,testserver").split(",")
    if host.strip()
]

SECRET_SEED = os.getenv("SPYGYM_SECRET_SEED", "spygym-dev-secret-change-me")
TOKEN_TTL_HOURS = int(os.getenv("SPYGYM_TOKEN_TTL_HOURS", "12"))
ADMIN_NAME = os.getenv("SPYGYM_ADMIN_NAME", "Administrador SPYGYM")
ADMIN_EMAIL = os.getenv("SPYGYM_ADMIN_EMAIL", "admin@spygym.local")
ADMIN_PASSWORD = os.getenv("SPYGYM_ADMIN_PASSWORD", "Admin@123")

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
