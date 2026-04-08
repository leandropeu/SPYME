"""
app/routers/dvr_remote.py

Remote access helpers for DVRs.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import parse_qsl, quote, urljoin, urlparse

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import DVR
from ..services.auth import ROLE_ADMIN, ROLE_OPERATOR, get_current_user, require_roles, resolve_user_by_token
from ..services.dvr_remote import get_channels, get_dvr_web_url, list_recordings, reboot_dvr
from ..services.vendors import build_http_url, build_httpx_auth


router = APIRouter(prefix="/dvr-remote", tags=["dvr-remote"], dependencies=[Depends(get_current_user)])
root_router = APIRouter(tags=["dvr-console-root"])


async def _get_dvr(dvr_id: int, session: AsyncSession) -> DVR:
    dvr = await session.get(DVR, dvr_id)
    if not dvr:
        raise HTTPException(status_code=404, detail="DVR nao encontrado.")
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
        raise HTTPException(status_code=400, detail="URL de destino invalida para este DVR.")
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


def _rewrite_console_text(content: str, *, dvr_id: int) -> str:
    console_prefix = f"/api/dvr-remote/{dvr_id}/console"
    rewritten = re.sub(r'([\'"])/(ISAPI|SDK)/', rf"\1{console_prefix}/\2/", content)
    rewritten = re.sub(r'(?<![A-Za-z0-9_])/(ISAPI|SDK)/', rf"{console_prefix}/\1/", rewritten)
    return rewritten


async def _proxy_dvr_request(
    dvr: DVR,
    *,
    method: str = "GET",
    target: str,
    timeout: httpx.Timeout | float,
    follow_redirects: bool,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
) -> httpx.Response:
    auth = build_httpx_auth(dvr)
    async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=follow_redirects) as client:
        return await client.request(method, target, auth=auth, headers=headers, content=content)


def _build_streaming_response(
    resp: httpx.Response,
    *,
    body: bytes | None = None,
    token: str | None = None,
    console_dvr_id: int | None = None,
) -> StreamingResponse:
    headers = dict(resp.headers)
    for header_name in (
        "x-frame-options",
        "content-security-policy",
        "x-content-type-options",
        "content-length",
        "Content-Length",
    ):
        headers.pop(header_name, None)

    response = StreamingResponse(
        iter([body if body is not None else resp.content]),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/html"),
        headers=headers,
    )
    if token:
        response.set_cookie("spygym_token", token, httponly=True, samesite="lax", path="/api/")
        response.set_cookie("spygym_console_token", token, httponly=True, samesite="lax", path="/")
    if console_dvr_id is not None:
        response.set_cookie("spygym_dvr_console", str(console_dvr_id), httponly=True, samesite="lax", path="/")
    return response


async def _proxy_console_request(
    *,
    dvr: DVR,
    dvr_id: int,
    request: Request | None,
    target_path: str,
    token: str | None,
) -> StreamingResponse:
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(request.url.query if request else "", keep_blank_values=True)
        if key != "token"
    ]
    query_suffix = (
        "?" + "&".join(f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in query_pairs)
        if query_pairs
        else ""
    )
    target = _validate_dvr_target(dvr, f"{get_dvr_web_url(dvr)}/{target_path.lstrip('/')}{query_suffix}")

    forwarded_headers: dict[str, str] = {}
    if request:
        for key, value in request.headers.items():
            if key.lower() in {"host", "cookie", "content-length", "authorization"}:
                continue
            forwarded_headers[key] = value

    body = await request.body() if request else b""
    resp = await _proxy_dvr_request(
        dvr,
        method=request.method if request else "GET",
        target=target,
        timeout=20.0,
        follow_redirects=True,
        headers=forwarded_headers,
        content=body or None,
    )

    media_type = resp.headers.get("content-type", "text/html")
    response_body = resp.content
    if any(marker in media_type.lower() for marker in ("text/html", "javascript", "json", "text/plain")):
        response_body = _rewrite_console_text(resp.text, dvr_id=dvr_id).encode(
            resp.encoding or "utf-8",
            errors="replace",
        )

    return _build_streaming_response(resp, body=response_body, token=token, console_dvr_id=dvr_id)


@router.get("/{dvr_id}/web-url")
async def dvr_web_url(dvr_id: int, session: AsyncSession = Depends(get_db)):
    dvr = await _get_dvr(dvr_id, session)
    return {
        "url": get_dvr_web_url(dvr),
        "note": "Alguns DVRs bloqueiam iframe. Use abrir em nova aba como fallback.",
    }


@router.get("/{dvr_id}/channels")
async def dvr_channels(dvr_id: int, session: AsyncSession = Depends(get_db)):
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
    dvr = await _get_dvr(dvr_id, session)
    if not start:
        from datetime import timedelta

        end = datetime.utcnow()
        start = end - timedelta(hours=24)
    try:
        recordings = await list_recordings(dvr, channel, start, end)
        return {"dvr_id": dvr_id, "channel": channel, "total": len(recordings), "recordings": recordings}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao listar gravacoes: {exc}")


@router.post("/{dvr_id}/reboot")
async def dvr_reboot(
    dvr_id: int,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN)),
):
    dvr = await _get_dvr(dvr_id, session)
    try:
        ok = await reboot_dvr(dvr)
        if not ok:
            raise HTTPException(status_code=502, detail="DVR nao confirmou o reboot.")
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
    dvr = await _get_dvr(dvr_id, session)
    base = get_dvr_web_url(dvr)
    target = _validate_dvr_target(dvr, f"{base}/{path.lstrip('/')}")
    token = request.query_params.get("token") if request else None

    try:
        resp = await _proxy_dvr_request(dvr, target=target, timeout=10.0, follow_redirects=True)
        media_type = resp.headers.get("content-type", "text/html")
        body = resp.content
        if "text/html" in media_type.lower():
            body = _rewrite_proxy_html(resp.text, dvr_id=dvr_id, token=token, current_path=path).encode(
                resp.encoding or "utf-8",
                errors="replace",
            )
        return _build_streaming_response(resp, body=body, token=token)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessivel. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.api_route("/{dvr_id}/console", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@router.api_route("/{dvr_id}/console/", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@router.api_route("/{dvr_id}/console/{proxy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def dvr_web_console(
    dvr_id: int,
    proxy_path: str = "",
    request: Request = None,
    session: AsyncSession = Depends(get_db),
    _: object = Depends(require_roles(ROLE_ADMIN, ROLE_OPERATOR)),
):
    dvr = await _get_dvr(dvr_id, session)
    token = (request.query_params.get("token") if request else None) or (request.cookies.get("spygym_token") if request else None)
    target_path = f"/{proxy_path.lstrip('/')}" if proxy_path else "/"

    try:
        return await _proxy_console_request(
            dvr=dvr,
            dvr_id=dvr_id,
            request=request,
            target_path=target_path,
            token=token,
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessivel. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@root_router.api_route("/ISAPI/{proxy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@root_router.api_route("/SDK/{proxy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def dvr_console_root_proxy(
    proxy_path: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    spygym_dvr_console: str | None = Cookie(default=None),
    spygym_console_token: str | None = Cookie(default=None),
):
    if not spygym_dvr_console or not spygym_dvr_console.isdigit():
        raise HTTPException(status_code=400, detail="Console do DVR nao inicializado.")
    user = await resolve_user_by_token(session, spygym_console_token)
    if user.role not in {ROLE_ADMIN, ROLE_OPERATOR}:
        raise HTTPException(status_code=403, detail="Perfil sem permissao para esta acao.")

    dvr_id = int(spygym_dvr_console)
    dvr = await _get_dvr(dvr_id, session)
    root_name = request.url.path.strip("/").split("/", 1)[0]
    target_path = f"/{root_name}/{proxy_path.lstrip('/')}"

    try:
        return await _proxy_console_request(
            dvr=dvr,
            dvr_id=dvr_id,
            request=request,
            target_path=target_path,
            token=request.cookies.get("spygym_token"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="DVR inacessivel. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{dvr_id}/recordings/proxy")
async def proxy_recording(
    dvr_id: int,
    playback_url: str,
    download: bool = False,
    session: AsyncSession = Depends(get_db),
):
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
        raise HTTPException(status_code=502, detail="DVR inacessivel. Verifique host e porta.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao acessar gravacao: {exc}")
