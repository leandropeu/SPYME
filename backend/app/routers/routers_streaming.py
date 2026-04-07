"""
app/routers/streaming.py

Endpoints de streaming de câmeras:
  GET /streaming/{camera_id}/start     — inicia HLS via ffmpeg
  GET /streaming/{camera_id}/stop      — encerra HLS
  GET /streaming/{camera_id}/hls       — serve playlist .m3u8
  GET /streaming/{camera_id}/vlc-link  — retorna link vlc://
  GET /streaming/status                — streams ativos
"""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import get_db
from ..models import Camera
from ..services.auth import get_current_user
from ..services.streaming import (
    build_vlc_link,
    ffmpeg_available,
    get_stream_info,
    hls_playlist_ready,
    hls_playlist_path,
    is_stream_active,
    start_hls_stream,
    stop_hls_stream,
)

router = APIRouter(prefix="/streaming", tags=["streaming"], dependencies=[Depends(get_current_user)])


async def _get_camera(camera_id: int, session: AsyncSession) -> Camera:
    camera = await session.get(Camera, camera_id, options=[selectinload(Camera.dvr)])
    if not camera:
        raise HTTPException(status_code=404, detail="Câmera não encontrada.")
    return camera


@router.post("/{camera_id}/start")
async def start_stream(camera_id: int, session: AsyncSession = Depends(get_db)):
    """Inicia o stream HLS da câmera via ffmpeg."""
    if not ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="ffmpeg não encontrado no servidor. Instale em https://www.gyan.dev/ffmpeg/builds/ e adicione ao PATH.",
        )
    camera = await _get_camera(camera_id, session)
    result = await start_hls_stream(camera, camera.dvr)
    status = result.get("status")
    attempts = result.get("attempts") or []

    if status == "unavailable":
        raise HTTPException(status_code=502, detail="Não foi possível iniciar o stream. Verifique o RTSP do DVR.")
    if status == "start_failed":
        raise HTTPException(status_code=502, detail="Não foi possível iniciar o stream. Verifique o RTSP do DVR.")
    if status == "timeout":
        attempted_paths = []
        for attempt in attempts:
            rtsp_url = attempt.get("rtsp_path") or ""
            if "/Streaming/Channels/" in rtsp_url:
                attempted_paths.append(rtsp_url.split("/Streaming/Channels/", 1)[1])
        attempted_summary = ", ".join(attempted_paths) if attempted_paths else "stream configurado"
        raise HTTPException(
            status_code=504,
            detail=f"O DVR nao respondeu com video RTSP a tempo. Tentativas: {attempted_summary}. Verifique RTSP, stream principal/substream e sinal do canal no DVR.",
        )
    if status != "ready":
        raise HTTPException(status_code=500, detail="Estado inesperado ao iniciar o stream.")
    return {"message": "Stream iniciado.", "hls_url": f"/api/streaming/{camera_id}/hls"}


@router.post("/{camera_id}/stop")
async def stop_stream(camera_id: int):
    """Encerra o stream HLS da câmera."""
    await stop_hls_stream(camera_id)
    return {"message": "Stream encerrado."}


@router.get("/{camera_id}/hls")
async def serve_hls_playlist(camera_id: int, token: str | None = None):
    """Serve o arquivo .m3u8 para o player HLS no browser."""
    for _ in range(20):
        if hls_playlist_ready(camera_id):
            break
        await asyncio.sleep(0.5)
    playlist = hls_playlist_path(camera_id)
    if not hls_playlist_ready(camera_id):
        raise HTTPException(status_code=404, detail="Stream não iniciado. Chame /start primeiro.")
    if not token:
        return FileResponse(str(playlist), media_type="application/vnd.apple.mpegurl")

    content = playlist.read_text(encoding="utf-8")
    rewritten_lines: list[str] = []
    encoded_token = quote(token, safe="")
    for line in content.splitlines():
        if line and not line.startswith("#") and "token=" not in line:
            separator = "&" if "?" in line else "?"
            line = f"{line}{separator}token={encoded_token}"
        rewritten_lines.append(line)
    return PlainTextResponse("\n".join(rewritten_lines), media_type="application/vnd.apple.mpegurl")


@router.get("/{camera_id}/hls/{segment}")
async def serve_hls_segment(camera_id: int, segment: str):
    """Serve os segmentos .ts do stream HLS."""
    seg_path = hls_playlist_path(camera_id).parent / segment
    if not seg_path.exists() or seg_path.suffix != ".ts":
        raise HTTPException(status_code=404, detail="Segmento não encontrado.")
    return FileResponse(str(seg_path), media_type="video/mp2t")


@router.get("/{camera_id}/vlc-link")
async def get_vlc_link(camera_id: int, session: AsyncSession = Depends(get_db)):
    """Retorna link vlc:// para abrir o stream direto no VLC instalado no computador do usuário."""
    camera = await _get_camera(camera_id, session)
    link = build_vlc_link(camera, camera.dvr)
    if not link:
        raise HTTPException(status_code=422, detail="Não foi possível gerar o link VLC. Configure stream_url ou stream_path.")
    return {"vlc_link": link, "rtsp_url": link.replace("vlc://", "")}


@router.get("/status")
async def stream_status():
    """Lista todos os streams HLS ativos no momento."""
    return {"ffmpeg_available": ffmpeg_available(), "streams": get_stream_info()}
