from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit


BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def _origin_from_url(raw_url: str, *, keep_port: bool) -> str:
    if not raw_url:
        return ""
    parsed = urlsplit(raw_url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    if keep_port and parsed.port:
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    return f"{parsed.scheme}://{parsed.hostname}"


_load_local_env(BACKEND_DIR / ".env")

DATA_DIR = Path(os.getenv("SPYGYM_DATA_DIR", BACKEND_DIR / "data"))
BACKUP_DIR = Path(os.getenv("SPYGYM_BACKUP_DIR", DATA_DIR / "backups"))
DB_PATH = Path(os.getenv("SPYGYM_DB_PATH", DATA_DIR / "spygym.db"))

APP_NAME = "SPYGYM"
APP_ENV = os.getenv("SPYGYM_ENV", "development")
APP_HOST = _get_env("SPYGYM_HOST", "HOST", default="0.0.0.0")
APP_PORT = int(_get_env("SPYGYM_PORT", "PORT", default="8000"))

HEALTHCHECK_SECONDS = int(os.getenv("SPYGYM_HEALTHCHECK_SECONDS", "60"))
HEALTHCHECK_CONCURRENCY = int(os.getenv("SPYGYM_HEALTHCHECK_CONCURRENCY", "10"))
BACKUP_HOURS = int(os.getenv("SPYGYM_BACKUP_HOURS", "2"))
BACKUP_RETENTION_DAYS = int(os.getenv("SPYGYM_BACKUP_RETENTION_DAYS", "5"))
BACKUP_MAX_FILES = int(os.getenv("SPYGYM_BACKUP_MAX_FILES", str((24 // max(BACKUP_HOURS, 1)) * BACKUP_RETENTION_DAYS)))

AUTO_SEED_DEMO = os.getenv("SPYGYM_AUTO_SEED_DEMO", "true").lower() == "true"
PUBLIC_BASE_URL = _get_env("SPYGYM_BASE_URL", "BASE_URL", default=f"http://{APP_HOST}:{APP_PORT}")
PUBLIC_FRONTEND_ORIGIN = _get_env(
    "SPYGYM_FRONTEND_ORIGIN",
    default=_origin_from_url(PUBLIC_BASE_URL, keep_port=False),
)
PUBLIC_BACKEND_ORIGIN = _origin_from_url(PUBLIC_BASE_URL, keep_port=True)

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://191.252.212.6",
    "https://191.252.212.6",
    "http://191.252.212.6:5173",
    "https://191.252.212.6:5173",
]
for extra_origin in (PUBLIC_FRONTEND_ORIGIN, PUBLIC_BACKEND_ORIGIN):
    if extra_origin and extra_origin not in default_origins:
        default_origins.append(extra_origin)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "SPYGYM_ALLOWED_ORIGINS",
        ",".join(default_origins),
    ).split(",")
    if origin.strip()
]

default_hosts = ["localhost", "127.0.0.1", "0.0.0.0", "testserver", "191.252.212.6"]
for host_candidate in (urlsplit(PUBLIC_BASE_URL).hostname, urlsplit(PUBLIC_FRONTEND_ORIGIN).hostname):
    if host_candidate and host_candidate not in default_hosts:
        default_hosts.append(host_candidate)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("SPYGYM_ALLOWED_HOSTS", ",".join(default_hosts)).split(",")
    if host.strip()
]

SECRET_SEED = os.getenv("SPYGYM_SECRET_SEED", "spygym-dev-secret-change-me")
TOKEN_TTL_HOURS = int(os.getenv("SPYGYM_TOKEN_TTL_HOURS", "12"))
ADMIN_NAME = os.getenv("SPYGYM_ADMIN_NAME", "Administrador SPYGYM")
ADMIN_EMAIL = os.getenv("SPYGYM_ADMIN_EMAIL", "admin@spygym.local")
ADMIN_PASSWORD = os.getenv("SPYGYM_ADMIN_PASSWORD", "Admin@123")

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
