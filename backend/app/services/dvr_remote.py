"""
app/services/dvr_remote.py

Acesso remoto a DVRs:
  - Listagem de gravações (Hikvision ISAPI / Intelbras CGI)
  - Download de clipe de gravação
  - Configurações remotas (canais, PTZ, reinicialização)
  - URL da interface web do DVR para embed no frontend
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from ..models import DVR
from .vendors import build_http_url, build_httpx_auth, normalize_vendor

logger = logging.getLogger(__name__)
TIMEOUT = httpx.Timeout(10.0, read=30.0)


def _auth(dvr: DVR) -> httpx.Auth | tuple[str, str]:
    return build_httpx_auth(dvr)


def _xml_text(node: ET.Element, tag_name: str) -> str | None:
    child = node.find(f"{{*}}{tag_name}")
    if child is None:
        child = node.find(tag_name)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _truthy(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return normalized not in {"", "0", "false", "no", "off", "disabled"}


def _parse_hik_stream_id(raw_id: str | None) -> tuple[int, int] | None:
    if not raw_id:
        return None
    try:
        stream_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    if stream_id <= 0:
        return None
    return stream_id // 100, stream_id % 100


def _choose_hik_preferred_stream(profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not profiles:
        return None

    def rank(profile: dict[str, Any]) -> tuple[int, int]:
        codec = (profile.get("codec") or "").strip().upper()
        stream_no = int(profile.get("stream_no") or 99)
        if codec == "H.264" and stream_no == 2:
            return (0, stream_no)
        if codec == "H.264" and stream_no == 1:
            return (1, stream_no)
        if stream_no == 2:
            return (2, stream_no)
        if stream_no == 1:
            return (3, stream_no)
        return (4, stream_no)

    enabled_profiles = [profile for profile in profiles if profile.get("enabled")]
    pool = enabled_profiles or profiles
    return min(pool, key=rank)


def get_dvr_web_url(dvr: DVR) -> str:
    """URL da interface web do DVR para abrir em iframe ou nova aba."""
    return f"{dvr.protocol}://{dvr.host}:{dvr.port}"


def _build_hik_search_bodies(channel: int, start: datetime, end: datetime) -> list[str]:
    track_id = f"{channel}01"
    start_text = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_text = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    return [
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription>
  <searchID>spygym-search</searchID>
  <trackList>
    <trackID>{track_id}</trackID>
  </trackList>
  <timeSpanList>
    <timeSpan>
      <startTime>{start_text}</startTime>
      <endTime>{end_text}</endTime>
    </timeSpan>
  </timeSpanList>
  <maxResults>50</maxResults>
  <searchResultPosition>0</searchResultPosition>
  <metadataList>
    <metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor>
  </metadataList>
</CMSearchDescription>""",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
  <searchID>spygym-search</searchID>
  <trackIDList>
    <trackID>{track_id}</trackID>
  </trackIDList>
  <timeSpanList>
    <timeSpan>
      <startTime>{start_text}</startTime>
      <endTime>{end_text}</endTime>
    </timeSpan>
  </timeSpanList>
  <maxResults>50</maxResults>
  <searchResultPosition>0</searchResultPosition>
</CMSearchDescription>""",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">
  <searchID>spygym-search</searchID>
  <trackIDList>
    <trackID>{track_id}</trackID>
  </trackIDList>
  <timeSpanList>
    <timeSpan>
      <startTime>{start_text}</startTime>
      <endTime>{end_text}</endTime>
    </timeSpan>
  </timeSpanList>
  <maxResults>50</maxResults>
  <searchResultPosition>0</searchResultPosition>
</CMSearchDescription>""",
    ]


# ── Hikvision ISAPI ───────────────────────────────────────────

async def hik_list_recordings(
    dvr: DVR,
    channel: int,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Lista gravações de um canal Hikvision via ISAPI."""
    url = build_http_url(dvr, f"/ISAPI/ContentMgmt/search")
    resp: httpx.Response | None = None
    last_bad_xml_error: httpx.HTTPStatusError | None = None

    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        for body in _build_hik_search_bodies(channel, start, end):
            candidate = await client.post(
                url,
                content=body,
                auth=_auth(dvr),
                headers={"Content-Type": "application/xml; charset=UTF-8"},
            )
            try:
                candidate.raise_for_status()
                resp = candidate
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 400 and "badXmlContent" in exc.response.text:
                    last_bad_xml_error = exc
                    continue
                raise

    if resp is None:
        raise ValueError(
            "Este firmware Hikvision recusou a busca ISAPI de gravacoes. "
            "Use a interface web/proxy do DVR para playback ate ajustarmos esse modelo."
        ) from last_bad_xml_error

    recordings = []
    try:
        root = ET.fromstring(resp.text)
        for item in root.findall(".//{*}searchMatchItem"):
            recordings.append({
                "start": _xml_text(item, "startTime"),
                "end": _xml_text(item, "endTime"),
                "playback_url": build_http_url(
                    dvr,
                    f"/ISAPI/ContentMgmt/download?playbackURI={_xml_text(item, 'playbackURI') or ''}",
                ),
                "type": _xml_text(item, "recordType"),
            })
    except ET.ParseError as exc:
        logger.warning("Falha ao parsear resposta de gravações: %s", exc)

    return recordings


async def hik_get_channels(dvr: DVR) -> list[dict[str, Any]]:
    """Lista canais de vídeo do DVR Hikvision."""
    input_url = build_http_url(dvr, "/ISAPI/System/Video/inputs/channels")
    streaming_url = build_http_url(dvr, "/ISAPI/Streaming/channels")

    stream_profiles_by_channel: dict[int, list[dict[str, Any]]] = {}
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        resp = await client.get(input_url, auth=_auth(dvr))
        resp.raise_for_status()

        try:
            streaming_resp = await client.get(streaming_url, auth=_auth(dvr))
            streaming_resp.raise_for_status()
            streaming_root = ET.fromstring(streaming_resp.text)
            for profile_node in streaming_root.findall(".//{*}StreamingChannel"):
                raw_id = _xml_text(profile_node, "id")
                parsed = _parse_hik_stream_id(raw_id)
                if not parsed:
                    continue
                channel_id, stream_no = parsed
                stream_profiles_by_channel.setdefault(channel_id, []).append(
                    {
                        "id": raw_id,
                        "stream_no": stream_no,
                        "codec": _xml_text(profile_node, "videoCodecType"),
                        "enabled": _truthy(_xml_text(profile_node, "enabled") or "true"),
                    }
                )
        except Exception:
            stream_profiles_by_channel = {}

    channels = []
    try:
        root = ET.fromstring(resp.text)
        for ch in root.findall(".//{*}VideoInputChannel"):
            channel_id = _xml_text(ch, "id")
            parsed_channel_id = int(channel_id or 0) if (channel_id or "").isdigit() else 0
            res_desc = _xml_text(ch, "resDesc")
            preferred_profile = _choose_hik_preferred_stream(stream_profiles_by_channel.get(parsed_channel_id, []))
            channels.append(
                {
                    "id": channel_id,
                    "name": _xml_text(ch, "name"),
                    "enabled": _xml_text(ch, "enabled") or _xml_text(ch, "videoInputEnabled"),
                    "res_desc": res_desc,
                    "has_video": bool(res_desc and res_desc.strip().upper() != "NO VIDEO"),
                    "preferred_stream_path": f"Streaming/Channels/{preferred_profile['id']}" if preferred_profile else None,
                    "preferred_codec": preferred_profile.get("codec") if preferred_profile else None,
                }
            )
    except ET.ParseError:
        pass
    return channels


async def hik_reboot(dvr: DVR) -> bool:
    """Reinicia o DVR Hikvision remotamente."""
    url = build_http_url(dvr, "/ISAPI/System/reboot")
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        resp = await client.put(url, auth=_auth(dvr))
        return resp.status_code in (200, 201, 204)


# ── Intelbras CGI ─────────────────────────────────────────────

async def intelbras_list_recordings(
    dvr: DVR,
    channel: int,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Lista gravações de um canal Intelbras via CGI."""
    params = {
        "action": "find",
        "channel": channel,
        "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
        "endTime":   end.strftime("%Y-%m-%d %H:%M:%S"),
        "type":      "all",
    }
    url = build_http_url(dvr, "/cgi-bin/mediaFileFind.cgi")
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        resp = await client.get(url, params=params, auth=_auth(dvr))
        resp.raise_for_status()

    # Intelbras retorna texto linha a linha: key=value
    recordings = []
    current: dict[str, str] = {}
    for line in resp.text.splitlines():
        line = line.strip()
        if "=" in line:
            k, _, v = line.partition("=")
            current[k.strip()] = v.strip()
        elif not line and current:
            if "StartTime" in current:
                recordings.append({
                    "start": current.get("StartTime"),
                    "end":   current.get("EndTime"),
                    "type":  current.get("Type", "regular"),
                    "playback_url": None,  # Intelbras não tem URL de download direto via CGI padrão
                })
            current = {}
    return recordings


async def intelbras_reboot(dvr: DVR) -> bool:
    """Reinicia o DVR Intelbras remotamente."""
    url = build_http_url(dvr, "/cgi-bin/magicBox.cgi?action=reboot")
    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        resp = await client.get(url, auth=_auth(dvr))
        return resp.status_code == 200


# ── Roteador unificado ────────────────────────────────────────

async def list_recordings(
    dvr: DVR,
    channel: int,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    vendor = normalize_vendor(dvr.vendor)
    if vendor == "hikvision":
        return await hik_list_recordings(dvr, channel, start, end)
    if vendor == "intelbras":
        return await intelbras_list_recordings(dvr, channel, start, end)
    raise ValueError(f"Vendor '{vendor}' não suportado para listagem de gravações.")


async def reboot_dvr(dvr: DVR) -> bool:
    vendor = normalize_vendor(dvr.vendor)
    if vendor == "hikvision":
        return await hik_reboot(dvr)
    if vendor == "intelbras":
        return await intelbras_reboot(dvr)
    raise ValueError(f"Vendor '{vendor}' não suportado para reboot remoto.")


async def get_channels(dvr: DVR) -> list[dict[str, Any]]:
    vendor = normalize_vendor(dvr.vendor)
    if vendor == "hikvision":
        return await hik_get_channels(dvr)
    # Intelbras não tem endpoint CGI padrão para listar canais
    return [{"id": str(i), "name": f"Canal {i}", "enabled": "true"}
            for i in range(1, dvr.channel_count + 1)]
