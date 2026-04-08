"""
app/routers/dvr_remote.py

Acesso remoto a DVRs:
  GET  /dvr-remote/{dvr_id}/web-url       — URL da interface web do DVR
  GET  /dvr-remote/{dvr_id}/channels      — lista canais
  GET  /dvr-remote/{dvr_id}/recordings    — lista gravações
  POST /dvr-remote/{dvr_id}/reboot        — reinicia o DVR remotamente
  GET  /dvr-remote/{dvr_id}/proxy         — proxy da interface web (para iframe)
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote, urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import httpx

from ..db import get_db
from ..models import DVR
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles
from ..services.dvr_remote import get_channels, get_dvr_web_url, list_recordings, reboot_dvr
from ..services.vendors import build_http_url, build_httpx_auth

router = APIRouter(prefix="/dvr-remote", tags=["dvr-remote"], dependencies=[Depends(get_current_user)])


async def _get_dvr(dvr_id: int, session: AsyncSession) -> DVR:
    dvr = await session.get(DVR, dvr_id)
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR não encontrado.")
    return dvr


def _validate_dvr_target(dvr: DVR, target: str) -> str:
    resolved_target = build_http_url(dvr, target)
    base = urlparse(get_dvr_web_url(dvr))
    parsed = urlparse(resolved_target)
    if (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)) != (
        base.scheme,
        base.hostname,
        base.port or (443 if base.scheme == "https" else 80),
    ):
        raise HTTPException(status_code=400, detail="URL de destino inválida para este DVR.")
    return resolved_target


def _build_proxy_url(dvr_id: int, path: str, token: str | None) -> str:
    encoded_path = quote(path or "/", safe="/:?=&%")
    url = f"/api/dvr-remote/{dvr_id}/proxy?path={encoded_path}"
    if token:
        url = f"{url}&token={quote(token, safe='')}"
    return url


def _resolve_proxy_path(current_path: str, target: str) -> str | None:
    value = (target or "").strip()
    if not value or value.startswith(("#", "javascript:", "data:", "mailto:", "tel:")):
        return None
    if value.startswith(("http://", "https://")):
        return value
    return urljoin(current_path if current_path.startswith("/") else f"/{current_path}", value)


def _rewrite_proxy_html(content: str, *, dvr_id: int, token: str | None, current_path: str) -> str:
    def replace_attr(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote_char = match.group(2)
        original = match.group(3)
        resolved = _resolve_proxy_path(current_path, original)
        if not resolved or resolved.startswith(("http://", "https://")):
            return match.group(0)
        return f"{attr}={quote_char}{_build_proxy_url(dvr_id, resolved, token)}{quote_char}"

    def replace_location(match: re.Match[str]) -> str:
        original = match.group(1)
        resolved = _resolve_proxy_path(current_path, original)
        if not resolved or resolved.startswith(("http://", "https://")):
            return match.group(0)
        return match.group(0).replace(original, _build_proxy_url(dvr_id, resolved, token))

    rewritten = re.sub(r'(?i)\b(href|src|action)=(["\'])([^"\']+)\2', replace_attr, content)
    rewritten = re.sub(r'(?i)window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', replace_location, rewritten)
    return rewritten


async def _proxy_dvr_request(
    dvr: DVR,
    *,
    target: str,
    timeout: httpx.Timeout | float,
    follow_redirects: bool,
) -> httpx.Response:
    auth = build_httpx_auth(dvr)
    async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=follow_redirects) as client:
        return await client.get(target, auth=auth)


def _build_streaming_response(
    resp: httpx.Response,
    *,
    body: bytes | None = None,
    token: str | None = None,
) -> StreamingResponse:
    headers = dict(resp.headers)
    for h in ("x-frame-options", "content-security-policy", "x-content-type-options", "content-length", "Content-Length"):
        headers.pop(h, None)

    response = StreamingResponse(
        iter([body if body is not None else resp.content]),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/html"),
        headers=headers,
    )
    if token:
        response.set_cookie("spygym_token", token, httponly=True, samesite="lax", path="/api/")
    return response


@router.get("/{dvr_id}/web-url")
async def dvr_web_url(dvr_id: int, session: AsyncSession = Depends(get_db)):
    """Retorna a URL da interface web do DVR para abrir em nova aba ou iframe."""
    dvr = await _get_dvr(dvr_id, session)
    url = get_dvr_web_url(dvr)
    return {
        "url": url,
        "note": "Alguns DVRs bloqueiam iframe (X-Frame-Options). Use 'Abrir em nova aba' como fallback.",
    }


@router.get("/{dvr_id}/channels")
async def dvr_channels(dvr_id: int, session: AsyncSession = Depends(get_db)):
    """Lista os canais de vídeo do DVR."""
    dvr = await _get_dvr(dvr_id, session)
    try:
        channels = await get_channels(dvr)
        return {"dvr_id": dvr_id, "channels": channels}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar canais: {exc}")


@router.get("/{dvr_id}/recordings")
async def dvr_recordings(
    dvr_id: int,
    channel: int = Query(default=1, ge=1),
    start: datetime = Query(default=None),
    end: datetime = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """Lista gravações de um canal do DVR em um período."""
    dvr = await _get_dvr(dvr_id, session)
    if not start:
        from datetime import timedelta
        end = datetime.utcnow()
        start = end - timedelta(hours=24)
    try:
        recordings = await list_recordings(dvr, channel, start, end)
        return {"dvr_id": dvr_id, "channel": channel, "total": len(recordings), "recordings": recordings}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao listar gravações: {exc}")


@router.post("/{dvr_id}/reboot")
async def dvr_reboot(
    dvr_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN)),
):
    """Reinicia o DVR remotamente. Apenas admin."""
    dvr = await _get_dvr(dvr_id, session)
    try:
        ok = await reboot_dvr(dvr)
        if not ok:
            raise HTTPException(status_code=502, detail="DVR não confirmou o reboot.")
        return {"message": f"DVR '{dvr.name}' reiniciando..."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao reiniciar DVR: {exc}")


@router.get("/{dvr_id}/proxy")
async def dvr_web_proxy(
    dvr_id: int,
    path: str = Query(default="/"),
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    """
    Proxy reverso para a interface web do DVR.
    Permite embutir a tela do DVR no SPYGYM contornando bloqueios de iframe.
    Use com cuidado — expõe a interface completa do DVR autenticado.
    """
    dvr = await _get_dvr(dvr_id, session)
    base = get_dvr_web_url(dvr)
    target = _validate_dvr_target(dvr, f"{base}/{path.lstrip('/')}")
    token = request.query_params.get("token") if request else None

    try:
        resp = await _proxy_dvr_request(dvr, target=target, timeout=10.0, follow_redirects=True)

        # Remove cabeçalhos que bloqueiam iframe
        headers = dict(resp.headers)
        for h in ("x-frame-options", "content-security-policy", "x-content-type-options"):
            headers.pop(h, None)
        headers.pop("X-Frame-Options", None)
        headers.pop("content-length", None)
        headers.pop("Content-Length", None)

        media_type = resp.headers.get("content-type", "text/html")
        body = resp.content
        if "text/html" in media_type.lower():
            body = _rewrite_proxy_html(resp.text, dvr_id=dvr_id, token=token, current_path=path).encode(
                resp.encoding or "utf-8",
                errors="replace",
            )

        return _build_streaming_response(resp, body=body, token=token)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessível. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{dvr_id}/console")
@router.get("/{dvr_id}/console/")
@router.get("/{dvr_id}/console/{proxy_path:path}")
async def dvr_web_console(
    dvr_id: int,
    proxy_path: str = "",
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await _get_dvr(dvr_id, session)
    token = request.query_params.get("token") if request else None
    target_path = f"/{proxy_path.lstrip('/')}" if proxy_path else "/"
    target = _validate_dvr_target(dvr, f"{get_dvr_web_url(dvr)}/{target_path.lstrip('/')}")

    try:
        resp = await _proxy_dvr_request(dvr, target=target, timeout=10.0, follow_redirects=True)
        return _build_streaming_response(resp, token=token)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessÃ­vel. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{dvr_id}/recordings/proxy")
async def proxy_recording(
    dvr_id: int,
    playback_url: str,
    download: bool = False,
    session: AsyncSession = Depends(get_db),
):
    """Faz proxy autenticado de um clipe de gravação do DVR para reprodução/download."""
    dvr = await _get_dvr(dvr_id, session)
    target = _validate_dvr_target(dvr, playback_url)
    auth = build_httpx_auth(dvr)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, read=180.0), verify=False, follow_redirects=True) as client:
            resp = await client.get(target, auth=auth)

        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="dvr_{dvr_id}_recording.bin"'

        return StreamingResponse(
            iter([resp.content]),
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/octet-stream"),
            headers=headers,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessível. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar gravação: {exc}")
