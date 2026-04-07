from __future__ import annotations

import asyncio
import html
import shutil
import socket
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import httpx

from ..models import Camera, DVR
from ..security import decrypt_secret


HIKVISION_STATUS_PATH = "/ISAPI/System/status"
HIKVISION_DEVICE_INFO_PATH = "/ISAPI/System/deviceInfo"
HIKVISION_SNAPSHOT_TEMPLATE = "/ISAPI/Streaming/channels/{channel}01/picture"

# Intelbras varia bastante entre linhas. Os caminhos ficam configuraveis por cadastro,
# mas deixamos um fallback compativel com equipamentos que expõem CGI de snapshot.
INTELBRAS_STATUS_PATH = "/cgi-bin/magicBox.cgi?action=getSystemInfo"
INTELBRAS_SNAPSHOT_TEMPLATE = "/cgi-bin/snapshot.cgi?channel={channel_index}"
DEFAULT_FFMPEG_WINDOWS_PATH = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
_SNAPSHOT_CACHE_TTL = 8.0
_snapshot_cache: dict[int, tuple[float, bytes, str]] = {}


def normalize_vendor(vendor: str | None) -> str:
    return (vendor or "generic").strip().lower()


def build_base_url(dvr: DVR) -> str:
    return f"{dvr.protocol}://{dvr.host}:{dvr.port}"


def build_http_url(dvr: DVR, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(f"{build_base_url(dvr)}/", path.lstrip("/"))


def locate_ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg") or (str(DEFAULT_FFMPEG_WINDOWS_PATH) if DEFAULT_FFMPEG_WINDOWS_PATH.exists() else None)


def build_httpx_auth(dvr: DVR) -> httpx.Auth | tuple[str, str]:
    username = dvr.username or "admin"
    password = decrypt_secret(dvr.password_encrypted) or ""
    if normalize_vendor(dvr.vendor) == "hikvision":
        return httpx.DigestAuth(username, password)
    return (username, password)


def build_rtsp_url(camera: Camera, dvr: DVR) -> str | None:
    if camera.stream_url:
        return camera.stream_url

    password = decrypt_secret(dvr.password_encrypted) or ""
    username = dvr.username or "admin"
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@" if username else ""
    vendor = normalize_vendor(camera.vendor or dvr.vendor)

    if camera.stream_path:
        path = camera.stream_path.lstrip("/")
        return f"rtsp://{credentials}{dvr.host}:554/{path}"

    ch = camera.channel_number
    if vendor == "hikvision":
        return f"rtsp://{credentials}{dvr.host}:554/Streaming/Channels/{ch}01"
    if vendor == "intelbras":
        return f"rtsp://{credentials}{dvr.host}:554/cam/realmonitor?channel={ch}&subtype=0"

    return f"rtsp://{credentials}{dvr.host}:554/stream{ch}"


def build_stream_reference(camera: Camera, dvr: DVR | None) -> str | None:
    if camera.stream_url:
        return camera.stream_url
    if not dvr:
        return None
    if camera.stream_path:
        if camera.stream_path.startswith(("rtsp://", "rtsps://", "http://", "https://")):
            return camera.stream_path
        return f"rtsp://{dvr.host}:554/{camera.stream_path.lstrip('/')}"
    return None


def resolve_snapshot_url(camera: Camera, dvr: DVR | None) -> str | None:
    if camera.snapshot_url:
        return camera.snapshot_url
    if not dvr:
        return None
    if camera.snapshot_path:
        return build_http_url(dvr, camera.snapshot_path)

    vendor = normalize_vendor(camera.vendor or dvr.vendor)
    if vendor == "hikvision":
        return build_http_url(dvr, HIKVISION_SNAPSHOT_TEMPLATE.format(channel=camera.channel_number))
    if vendor == "intelbras":
        return build_http_url(
            dvr,
            INTELBRAS_SNAPSHOT_TEMPLATE.format(channel_index=max(camera.channel_number - 1, 0)),
        )
    return None


def resolve_status_url(dvr: DVR) -> str | None:
    if dvr.api_status_path:
        return build_http_url(dvr, dvr.api_status_path)
    vendor = normalize_vendor(dvr.vendor)
    if vendor == "hikvision":
        return build_http_url(dvr, HIKVISION_STATUS_PATH)
    if vendor == "intelbras":
        return build_http_url(dvr, INTELBRAS_STATUS_PATH)
    return build_base_url(dvr)


def resolve_device_info_url(dvr: DVR) -> str | None:
    if dvr.device_info_path:
        return build_http_url(dvr, dvr.device_info_path)
    if normalize_vendor(dvr.vendor) == "hikvision":
        return build_http_url(dvr, HIKVISION_DEVICE_INFO_PATH)
    return None


async def tcp_ping(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(loop.run_in_executor(None, _tcp_open, host, port), timeout=timeout)
        return True
    except Exception:
        return False


def _tcp_open(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3):
        return None


def _parse_device_info(text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}

    values: dict[str, Any] = {}
    for tag in ("deviceName", "model", "serialNumber", "firmwareVersion"):
        node = root.find(f".//{{*}}{tag}")
        if node is None:
            node = root.find(tag)
        if node is not None and node.text:
            values[tag] = node.text.strip()
    return values


async def fetch_dvr_status(dvr: DVR) -> dict[str, Any]:
    started = time.perf_counter()
    url = resolve_status_url(dvr)
    device_info_url = resolve_device_info_url(dvr)
    http_status: int | None = None
    device_info: dict[str, Any] = {}
    auth = build_httpx_auth(dvr)

    try:
        async with httpx.AsyncClient(timeout=5.0, verify=False) as client:
            response = await client.get(url, auth=auth)
            http_status = response.status_code
            reachable = http_status in (200, 401, 403)
            if reachable and device_info_url:
                info_response = await client.get(device_info_url, auth=auth)
                if info_response.status_code in (200, 401, 403):
                    device_info = _parse_device_info(info_response.text)
            latency = round((time.perf_counter() - started) * 1000, 2)
            return {
                "reachable": reachable,
                "http_status": http_status,
                "latency_ms": latency,
                "device_info": device_info,
                "checked_via": "http",
            }
    except Exception:
        pass

    reachable = await tcp_ping(dvr.host, dvr.port)
    latency = round((time.perf_counter() - started) * 1000, 2)
    return {
        "reachable": reachable,
        "http_status": http_status,
        "latency_ms": latency,
        "device_info": device_info,
        "checked_via": "tcp",
    }


async def fetch_camera_snapshot(camera: Camera, dvr: DVR | None) -> tuple[bytes, str]:
    cached = _snapshot_cache.get(camera.id)
    if cached and time.time() - cached[0] < _SNAPSHOT_CACHE_TTL:
        return cached[1], cached[2]

    snapshot_url = resolve_snapshot_url(camera, dvr)
    if not snapshot_url:
        raise ValueError("Configure snapshot_path ou snapshot_url para esta camera.")

    auth = build_httpx_auth(dvr) if dvr else None
    last_error = "Snapshot indisponível."

    async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
        response = await client.get(snapshot_url, auth=auth)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "image/jpeg")
            _snapshot_cache[camera.id] = (time.time(), response.content, content_type)
            return response.content, content_type
        last_error = f"Snapshot HTTP {response.status_code}."

    if dvr:
        ffmpeg_bin = locate_ffmpeg_binary()
        rtsp_url = build_rtsp_url(camera, dvr)
        if ffmpeg_bin and rtsp_url:
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin,
                "-y",
                "-rtsp_transport",
                "tcp",
                "-i",
                rtsp_url,
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=12)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                stdout = b""

            if proc.returncode == 0 and stdout:
                _snapshot_cache[camera.id] = (time.time(), stdout, "image/jpeg")
                return stdout, "image/jpeg"

    raise ValueError(f"{last_error} Este DVR nao liberou snapshot por HTTP e o fallback RTSP falhou.")


def _parse_ppm_frame(frame: bytes) -> tuple[memoryview, int, int] | None:
    if not frame.startswith(b"P6"):
        return None

    tokens: list[bytes] = []
    idx = 2
    length = len(frame)

    while len(tokens) < 3 and idx < length:
        while idx < length and frame[idx] in b" \t\r\n":
            idx += 1
        if idx < length and frame[idx] == 35:  # '#'
            while idx < length and frame[idx] not in b"\r\n":
                idx += 1
            continue
        start = idx
        while idx < length and frame[idx] not in b" \t\r\n":
            idx += 1
        if start != idx:
            tokens.append(frame[start:idx])

    if len(tokens) < 3:
        return None

    width = int(tokens[0])
    height = int(tokens[1])
    max_value = int(tokens[2])
    if max_value <= 0:
        return None

    while idx < length and frame[idx] in b" \t\r\n":
        idx += 1

    pixels = memoryview(frame)[idx:]
    expected_size = width * height * 3
    if len(pixels) < expected_size:
        return None
    return pixels[:expected_size], width, height


def _looks_like_placeholder_frame(frame: bytes) -> bool:
    parsed = _parse_ppm_frame(frame)
    if not parsed:
        return True

    pixels, width, height = parsed
    sample_step = max((width * height) // 3000, 1)
    greenish = 0
    darkish = 0
    sampled = 0
    r_min = g_min = b_min = 255
    r_max = g_max = b_max = 0

    for pixel_index in range(0, width * height, sample_step):
        base = pixel_index * 3
        r = pixels[base]
        g = pixels[base + 1]
        b = pixels[base + 2]
        sampled += 1

        if g > 70 and g > r * 1.45 and g > b * 1.45:
            greenish += 1
        if r < 20 and g < 20 and b < 20:
            darkish += 1

        r_min = min(r_min, r)
        g_min = min(g_min, g)
        b_min = min(b_min, b)
        r_max = max(r_max, r)
        g_max = max(g_max, g)
        b_max = max(b_max, b)

    if not sampled:
        return True

    green_ratio = greenish / sampled
    dark_ratio = darkish / sampled
    channel_variation = (r_max - r_min) + (g_max - g_min) + (b_max - b_min)

    return green_ratio >= 0.82 or dark_ratio >= 0.96 or channel_variation <= 18


async def probe_camera_stream(camera: Camera, dvr: DVR | None, *, timeout: float = 10.0) -> dict[str, Any]:
    if not dvr:
        return {"reachable": False, "reason": "camera_sem_dvr"}

    ffmpeg_bin = locate_ffmpeg_binary()
    rtsp_url = build_rtsp_url(camera, dvr)
    if not ffmpeg_bin or not rtsp_url:
        return {"reachable": False, "reason": "stream_nao_configurado"}

    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin,
        "-v",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-map",
        "0:v:0",
        "-an",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "ppm",
        "pipe:1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return {"reachable": False, "reason": "timeout"}

    detail = (stderr or b"").decode("utf-8", errors="ignore").strip()
    if stdout:
        placeholder = _looks_like_placeholder_frame(stdout)
        return {
            "reachable": not placeholder,
            "reason": "placeholder_sem_sinal" if placeholder else "rtsp_ok",
            "detail": detail[:240],
        }

    return {"reachable": False, "reason": "rtsp_sem_quadro", "detail": detail[:240]}


def build_snapshot_placeholder(camera: Camera, dvr: DVR | None, detail: str | None = None) -> tuple[bytes, str]:
    detail_text = detail or "Snapshot indisponivel"
    if "403" in detail_text or "fallback RTSP falhou" in detail_text:
        detail_text = "Este modelo de DVR nao libera preview por imagem neste modo."
    subtitle = f"{camera.name} • Canal {camera.channel_number}"
    host = f"{dvr.host}:{dvr.port}" if dvr else "Camera sem DVR"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
  </defs>
  <rect width="960" height="540" fill="url(#bg)"/>
  <rect x="36" y="36" width="888" height="468" rx="28" fill="rgba(15,23,42,0.45)" stroke="rgba(148,163,184,0.25)"/>
  <text x="72" y="128" fill="#e2e8f0" font-family="Segoe UI, Arial, sans-serif" font-size="38" font-weight="700">{html.escape(camera.name)}</text>
  <text x="72" y="176" fill="#93c5fd" font-family="Segoe UI, Arial, sans-serif" font-size="24">{html.escape(subtitle)}</text>
  <text x="72" y="250" fill="#f8fafc" font-family="Segoe UI, Arial, sans-serif" font-size="30" font-weight="600">Preview temporariamente indisponivel</text>
  <text x="72" y="302" fill="#cbd5e1" font-family="Segoe UI, Arial, sans-serif" font-size="22">{html.escape(detail_text)}</text>
  <text x="72" y="344" fill="#94a3b8" font-family="Segoe UI, Arial, sans-serif" font-size="20">{html.escape(host)}</text>
  <text x="72" y="420" fill="#86efac" font-family="Segoe UI, Arial, sans-serif" font-size="22">Use "Ao vivo" para abrir o stream HLS ou o VLC autenticado.</text>
</svg>"""
    return svg.encode("utf-8"), "image/svg+xml"


def build_default_camera_payload(dvr: DVR, channel_number: int) -> dict[str, Any]:
    vendor = normalize_vendor(dvr.vendor)
    snapshot_path = None
    stream_path = None

    if vendor == "hikvision":
        snapshot_path = HIKVISION_SNAPSHOT_TEMPLATE.format(channel=channel_number)
        # Preferimos o substream (xx02) para maior compatibilidade com ffmpeg/HLS no navegador.
        stream_path = f"Streaming/Channels/{channel_number}02"
    elif vendor == "intelbras":
        snapshot_path = INTELBRAS_SNAPSHOT_TEMPLATE.format(channel_index=max(channel_number - 1, 0))
        stream_path = f"cam/realmonitor?channel={channel_number}&subtype=0"

    return {
        "name": f"Camera {channel_number:02d}",
        "vendor": vendor,
        "channel_number": channel_number,
        "snapshot_path": snapshot_path,
        "stream_path": stream_path,
    }
