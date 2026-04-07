"""
app/services/streaming.py

Streaming de câmeras:
  - Proxy HLS via ffmpeg (ao vivo no browser)
  - Geração de link vlc:// para abrir no VLC local
  - Snapshot atualizado

Requer ffmpeg instalado no servidor.
Windows: https://www.gyan.dev/ffmpeg/builds/ → ffmpeg-release-essentials.zip
         Extraia e adicione a pasta bin ao PATH do sistema.
Linux:   sudo apt install ffmpeg
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from ..models import Camera, DVR
from .vendors import build_rtsp_url, locate_ffmpeg_binary, normalize_vendor

logger = logging.getLogger(__name__)

# Diretório temporário para segmentos HLS
_HLS_DIR = Path(tempfile.gettempdir()) / "spygym_hls"
_HLS_DIR.mkdir(parents=True, exist_ok=True)

# Processos ffmpeg ativos: camera_id → asyncio.subprocess.Process
_active_streams: dict[int, asyncio.subprocess.Process] = {}
_stream_started: dict[int, float] = {}

STREAM_IDLE_TIMEOUT = 60  # segundos sem cliente → encerra ffmpeg
_HIKVISION_STREAM_ID_RE = re.compile(r"/Streaming/Channels/(?P<stream_id>\d+)(?=$|[/?#])", re.IGNORECASE)


def ffmpeg_available() -> bool:
    return locate_ffmpeg_binary() is not None


def build_vlc_link(camera: Camera, dvr: DVR | None) -> str | None:
    """Retorna link vlc:// para abrir o stream direto no VLC do usuário."""
    rtsp = build_rtsp_url(camera, dvr)
    if not rtsp:
        return None
    # vlc:// é um protocolo customizado que sistemas com VLC instalado reconhecem
    return f"vlc://{rtsp}"


def hls_dir_for(camera_id: int) -> Path:
    d = _HLS_DIR / str(camera_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def hls_playlist_path(camera_id: int) -> Path:
    return hls_dir_for(camera_id) / "stream.m3u8"


def clear_hls_artifacts(camera_id: int) -> None:
    out_dir = hls_dir_for(camera_id)
    for item in out_dir.glob("*"):
        if item.is_file():
            item.unlink(missing_ok=True)


def is_stream_active(camera_id: int) -> bool:
    proc = _active_streams.get(camera_id)
    return proc is not None and proc.returncode is None


def hls_playlist_ready(camera_id: int) -> bool:
    playlist = hls_playlist_path(camera_id)
    if not playlist.exists():
        return False
    try:
        content = playlist.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(line and not line.startswith("#") for line in content.splitlines())


async def _wait_for_hls_playlist(
    camera_id: int,
    proc: asyncio.subprocess.Process | None,
    wait_seconds: float,
    delay_seconds: float = 0.5,
) -> bool:
    attempts = max(1, int(wait_seconds / delay_seconds))
    for _ in range(attempts):
        if hls_playlist_ready(camera_id):
            return True
        if proc and proc.returncode is not None:
            logger.warning("Processo ffmpeg encerrou cedo para camera %s com codigo %s", camera_id, proc.returncode)
            return False
        await asyncio.sleep(delay_seconds)
    return hls_playlist_ready(camera_id)


def _hikvision_mainstream_fallback(rtsp_url: str) -> str | None:
    match = _HIKVISION_STREAM_ID_RE.search(rtsp_url)
    if not match:
        return None
    stream_id = match.group("stream_id")
    if not stream_id.endswith("02"):
        return None
    fallback_id = f"{stream_id[:-2]}01"
    return f"{rtsp_url[:match.start('stream_id')]}{fallback_id}{rtsp_url[match.end('stream_id'):]}"


def _rtsp_candidates(camera: Camera, dvr: DVR) -> list[str]:
    primary = build_rtsp_url(camera, dvr)
    if not primary:
        return []

    candidates = [primary]
    if normalize_vendor(camera.vendor or dvr.vendor) == "hikvision":
        fallback = _hikvision_mainstream_fallback(primary)
        if fallback and fallback not in candidates:
            candidates.append(fallback)
    return candidates


async def _spawn_hls_process(camera_id: int, ffmpeg_bin: str, rtsp_url: str) -> asyncio.subprocess.Process | None:
    out_dir = hls_dir_for(camera_id)
    clear_hls_artifacts(camera_id)
    playlist = out_dir / "stream.m3u8"

    cmd = [
        ffmpeg_bin, "-y",
        "-rtsp_transport", "tcp",
        "-use_wallclock_as_timestamps", "1",
        "-fflags", "+genpts+igndts+discardcorrupt",
        "-i", rtsp_url,
        "-map", "0:v:0",
        "-an",
        "-vf", "fps=10,scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-profile:v", "baseline",
        "-level", "3.1",
        "-g", "20",
        "-keyint_min", "20",
        "-sc_threshold", "0",
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "5",
        "-hls_flags", "delete_segments+independent_segments",
        "-hls_segment_filename", str(out_dir / "seg%03d.ts"),
        str(playlist),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _active_streams[camera_id] = proc
        _stream_started[camera_id] = time.time()
        logger.info("HLS stream iniciado para camera %s (pid=%s) usando %s", camera_id, proc.pid, rtsp_url)
        return proc
    except Exception as exc:
        logger.error("Falha ao iniciar ffmpeg para camera %s usando %s: %s", camera_id, rtsp_url, exc)
        return None


async def start_hls_stream(camera: Camera, dvr: DVR | None) -> dict[str, Any]:
    """
    Inicia o ffmpeg convertendo RTSP → HLS.
    Retorna:
      - status=ready: playlist HLS disponivel
      - status=unavailable: ffmpeg ausente, camera sem DVR ou RTSP indisponivel
      - status=start_failed: ffmpeg nao iniciou
      - status=timeout: ffmpeg iniciou, mas o HLS nao ficou pronto a tempo
    """
    if not ffmpeg_available():
        return {"status": "unavailable", "attempts": []}

    if not dvr:
        return {"status": "unavailable", "attempts": []}

    ffmpeg_bin = locate_ffmpeg_binary()
    rtsp_candidates = _rtsp_candidates(camera, dvr)
    if not ffmpeg_bin or not rtsp_candidates:
        return {"status": "unavailable", "attempts": []}

    if is_stream_active(camera.id):
        if hls_playlist_ready(camera.id):
            _stream_started[camera.id] = time.time()
            return {"status": "ready", "attempts": []}
        await stop_hls_stream(camera.id)

    total_wait_seconds = 45.0
    started_any = False
    attempts: list[dict[str, Any]] = []

    for index, rtsp_url in enumerate(rtsp_candidates):
        if index > 0:
            logger.warning("Tentando fallback de stream para camera %s: %s", camera.id, rtsp_url)

        proc = await _spawn_hls_process(camera.id, ffmpeg_bin, rtsp_url)
        if not proc:
            continue

        started_any = True
        is_last_candidate = index == len(rtsp_candidates) - 1
        wait_seconds = total_wait_seconds if is_last_candidate else min(10.0, total_wait_seconds)
        ready = await _wait_for_hls_playlist(camera.id, proc, wait_seconds=wait_seconds)
        attempts.append(
            {
                "rtsp_path": rtsp_url,
                "wait_seconds": wait_seconds,
                "process_returncode": proc.returncode,
                "ready": ready,
            }
        )
        if ready:
            return {"status": "ready", "attempts": attempts}

        logger.warning("HLS nao ficou pronto para camera %s usando %s", camera.id, rtsp_url)
        await stop_hls_stream(camera.id)
        total_wait_seconds = max(0.0, total_wait_seconds - wait_seconds)
        if total_wait_seconds <= 0:
            break

    clear_hls_artifacts(camera.id)
    if started_any:
        return {"status": "timeout", "attempts": attempts}

    return {"status": "start_failed", "attempts": attempts}


async def stop_hls_stream(camera_id: int) -> None:
    proc = _active_streams.pop(camera_id, None)
    _stream_started.pop(camera_id, None)
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
    logger.info("HLS stream encerrado para câmera %s", camera_id)


async def stop_all_streams() -> None:
    for camera_id in list(_active_streams.keys()):
        await stop_hls_stream(camera_id)


def get_stream_info() -> list[dict[str, Any]]:
    return [
        {
            "camera_id": cid,
            "active": is_stream_active(cid),
            "uptime_seconds": round(time.time() - _stream_started.get(cid, time.time())),
        }
        for cid in _active_streams
    ]
