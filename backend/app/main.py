from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import ALLOWED_HOSTS, ALLOWED_ORIGINS, APP_NAME, BACKUP_DIR, BACKUP_HOURS, BACKUP_RETENTION_DAYS, DB_PATH, HEALTHCHECK_SECONDS
from .db import SessionLocal, init_db
from .routers import auth, backups, cameras, cloud_accounts, dvr_remote, dvrs, events, streaming, units, users
from .services.auth import ROLE_ADMIN, ROLE_OPERATOR, authenticate_websocket, require_roles
from .services.backup import create_backup, set_broadcast_hook as set_backup_broadcast_hook
from .services.monitoring import run_health_check, set_broadcast_hook as set_monitoring_broadcast_hook
from .services.seed import seed_demo_data
from .services.streaming import stop_all_streams


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, payload: dict) -> None:
        if not self.connections:
            return
        message = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for connection in list(self.connections):
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)


manager = ConnectionManager()
scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)


async def scheduled_health_check() -> None:
    await run_health_check(skip_if_running=True)


def launch_health_check_task() -> None:
    async def runner() -> None:
        try:
            await run_health_check(skip_if_running=True)
        except Exception:
            logger.exception("Health check em background falhou.")
    asyncio.create_task(runner())


async def scheduled_backup() -> None:
    async with SessionLocal() as session:
        await create_backup(session)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_demo_data(session)

    set_monitoring_broadcast_hook(manager.broadcast)
    set_backup_broadcast_hook(manager.broadcast)

    scheduler.add_job(scheduled_health_check, "interval", seconds=HEALTHCHECK_SECONDS,
                      id="health_check_job", max_instances=1, replace_existing=True)
    scheduler.add_job(scheduled_backup, "interval", hours=BACKUP_HOURS,
                      id="backup_job", max_instances=1, replace_existing=True)
    scheduler.start()
    launch_health_check_task()
    yield
    scheduler.shutdown(wait=False)
    await stop_all_streams()


app = FastAPI(
    title=APP_NAME,
    version="1.1.0",
    description="Plataforma de monitoramento de cameras e DVRs para redes de academia.",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS or ["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS or ["*"])


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    is_proxy_response = "/proxy" in request.url.path
    if not is_proxy_response:
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.include_router(units.router,          prefix="/api")
app.include_router(dvrs.router,           prefix="/api")
app.include_router(cameras.router,        prefix="/api")
app.include_router(events.router,         prefix="/api")
app.include_router(backups.router,        prefix="/api")
app.include_router(auth.router,           prefix="/api")
app.include_router(cloud_accounts.router, prefix="/api")
app.include_router(streaming.router,      prefix="/api")
app.include_router(dvr_remote.router,     prefix="/api")
app.include_router(users.router,          prefix="/api")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": "1.1.0",
        "database": str(DB_PATH),
        "backup_dir": str(BACKUP_DIR),
        "backup_interval_hours": BACKUP_HOURS,
        "backup_retention_days": BACKUP_RETENTION_DAYS,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/monitor/run")
async def run_monitor(_: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR))):
    launch_health_check_task()
    return {"message": "Rotina de monitoramento disparada."}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client_host = getattr(websocket.client, "host", "unknown")
    client_port = getattr(websocket.client, "port", "unknown")
    token = websocket.query_params.get("token")
    token_suffix = token[-8:] if token else "missing"

    try:
        user = await authenticate_websocket(websocket)
    except HTTPException as exc:
        logger.warning(
            "WebSocket rejeitado para %s:%s, token=%s, motivo=%s",
            client_host,
            client_port,
            token_suffix,
            exc.detail,
        )
        await websocket.close(code=1008, reason=str(exc.detail))
        return
    except Exception:
        logger.exception(
            "Falha inesperada autenticando WebSocket para %s:%s, token=%s",
            client_host,
            client_port,
            token_suffix,
        )
        await websocket.close(code=1011, reason="auth_error")
        return

    await manager.connect(websocket)
    logger.info(
        "WebSocket conectado para %s:%s, usuario=%s, token=%s",
        client_host,
        client_port,
        user.email,
        token_suffix,
    )
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect as exc:
        logger.info(
            "WebSocket desconectado para %s:%s, usuario=%s, code=%s",
            client_host,
            client_port,
            user.email,
            getattr(exc, "code", "unknown"),
        )
        manager.disconnect(websocket)
    except Exception:
        logger.exception(
            "Erro no loop do WebSocket para %s:%s, usuario=%s",
            client_host,
            client_port,
            user.email,
        )
        manager.disconnect(websocket)
