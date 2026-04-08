from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import re
import shutil
import socket
import subprocess

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import DVR, Unit
from ..schemas import DiscoveredDvrHost, UnitDvrDiscoveryOut
from .network_discovery import fingerprint_dvr


DVR_PORTS = [80, 443, 554, 8000, 8080, 37777]
NMAP_PORT_PATTERN = re.compile(r"Host:\s+(\S+).*Ports:\s+(.*)")


@dataclass
class DiscoveryStats:
    created_count: int = 0
    updated_count: int = 0


def _normalize_vendor(vendor: str | None) -> str:
    return (vendor or "").strip().lower()


def _safe_network(cidr: str) -> ipaddress.IPv4Network:
    network = ipaddress.ip_network(cidr, strict=False)
    if network.version != 4:
        raise ValueError("Somente redes IPv4 sao suportadas para descoberta no momento.")
    if network.num_addresses > 1024:
        raise ValueError("A descoberta automatica esta limitada a redes com ate 1024 enderecos.")
    return network


def _parse_grepable_ports(output: str) -> dict[str, list[int]]:
    ports_by_host: dict[str, list[int]] = {}
    for line in output.splitlines():
        match = NMAP_PORT_PATTERN.search(line)
        if not match:
            continue
        host, ports_blob = match.groups()
        open_ports: list[int] = []
        for item in ports_blob.split(","):
            parts = item.strip().split("/")
            if len(parts) < 2 or parts[1] != "open":
                continue
            try:
                open_ports.append(int(parts[0]))
            except ValueError:
                continue
        if open_ports:
            ports_by_host[host] = sorted(set(open_ports))
    return ports_by_host


def _run_dvr_nmap_scan(cidr: str) -> tuple[dict[str, list[int]], str] | None:
    if not shutil.which("nmap"):
        return None
    ports = ",".join(str(port) for port in DVR_PORTS)
    result = subprocess.run(
        ["nmap", "-n", "-Pn", f"-p{ports}", "-oG", "-", cidr],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    return _parse_grepable_ports(result.stdout), "dvr-nmap-pn"


async def _probe_port(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _fallback_dvr_scan(cidr: str) -> tuple[dict[str, list[int]], str]:
    network = _safe_network(cidr)
    ports_by_host: dict[str, list[int]] = {}
    semaphore = asyncio.Semaphore(48)

    async def scan_host(host: str) -> None:
        async with semaphore:
            tasks = [asyncio.create_task(_probe_port(host, port)) for port in DVR_PORTS]
            results = await asyncio.gather(*tasks)
            matched_ports = [port for port, is_open in zip(DVR_PORTS, results) if is_open]
            if matched_ports:
                ports_by_host[host] = matched_ports

    await asyncio.gather(*(scan_host(str(ip)) for ip in network.hosts()))
    return ports_by_host, "dvr-tcp-fallback"


async def discover_dvr_candidates(cidr: str) -> tuple[dict[str, list[int]], str]:
    _safe_network(cidr)
    discovered = await asyncio.to_thread(_run_dvr_nmap_scan, cidr)
    if discovered and discovered[0]:
        return discovered
    return await _fallback_dvr_scan(cidr)


async def discover_unit_dvrs(
    session: AsyncSession,
    unit: Unit,
    *,
    persist: bool = True,
) -> UnitDvrDiscoveryOut:
    if not unit.vpn_network_cidr:
        raise ValueError("Preencha a rede da unidade em 'Rede remota VPN' para mapear os DVRs.")

    discovered_ports, scanner = await discover_dvr_candidates(unit.vpn_network_cidr)
    fingerprints = []
    for host in sorted(discovered_ports, key=socket.inet_aton):
        fingerprint = await fingerprint_dvr(host, discovered_ports[host])
        if fingerprint:
            fingerprints.append(fingerprint)

    existing_dvrs = (
        await session.execute(select(DVR).where(DVR.unit_id == unit.id).options(selectinload(DVR.cameras)))
    ).scalars().all()
    existing_by_host = {item.host: item for item in existing_dvrs}
    stats = DiscoveryStats()
    results: list[DiscoveredDvrHost] = []

    for candidate in fingerprints:
        vendor_key = _normalize_vendor(candidate.vendor)
        existing = existing_by_host.get(candidate.host)
        dvr_name = candidate.notes.split(".", 1)[0]

        if persist:
            if existing:
                changed = False
                if existing.vendor != vendor_key:
                    existing.vendor = vendor_key or existing.vendor
                    changed = True
                if candidate.model and existing.model != candidate.model:
                    existing.model = candidate.model
                    changed = True
                if candidate.protocol and existing.protocol != candidate.protocol:
                    existing.protocol = candidate.protocol
                    changed = True
                if candidate.port and existing.port != candidate.port:
                    existing.port = candidate.port
                    changed = True
                if not existing.notes or "descoberto automaticamente" not in existing.notes.lower():
                    existing.notes = (existing.notes or "").strip()
                    suffix = " Descoberto automaticamente pela varredura da unidade."
                    existing.notes = f"{existing.notes}{suffix}".strip()
                    changed = True
                if changed:
                    stats.updated_count += 1
            else:
                created = DVR(
                    unit_id=unit.id,
                    name=dvr_name,
                    vendor=vendor_key or "hikvision",
                    model=candidate.model,
                    host=candidate.host,
                    port=candidate.port or 80,
                    protocol=candidate.protocol or "http",
                    username="admin",
                    channel_count=16,
                    notes=f"{candidate.notes} Descoberto automaticamente pela varredura da unidade.",
                    status="unknown",
                    is_active=True,
                )
                session.add(created)
                await session.flush()
                existing_by_host[candidate.host] = created
                existing = created
                stats.created_count += 1

        results.append(
            DiscoveredDvrHost(
                host=candidate.host,
                name=dvr_name,
                vendor=candidate.vendor,
                model=candidate.model,
                protocol=candidate.protocol,
                port=candidate.port,
                open_ports=candidate.open_ports,
                username_hint="admin",
                notes=candidate.notes,
                matched_dvr_id=existing.id if existing else None,
                detection_source="scanner+fingerprint",
            )
        )

    if persist:
        await session.commit()

    return UnitDvrDiscoveryOut(
        unit_id=unit.id,
        unit_name=unit.name,
        network_cidr=unit.vpn_network_cidr,
        scanner=scanner,
        discovered_count=len(results),
        created_count=stats.created_count,
        updated_count=stats.updated_count,
        hosts=results,
    )
