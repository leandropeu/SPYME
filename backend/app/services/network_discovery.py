from __future__ import annotations

import asyncio
import ipaddress
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from typing import Iterable


COMMON_PORTS = [22, 23, 53, 80, 81, 88, 139, 161, 389, 443, 445, 554, 8000, 8080, 8291, 8728, 8729, 3389]
PRIMARY_SYN_PORTS = [80, 443, 445, 554, 8291, 3389, 53]
NMAP_HOST_PATTERN = re.compile(r"Host:\s+(\S+)\s+Status:\s+Up")
NMAP_PORT_PATTERN = re.compile(r"Host:\s+(\S+).*Ports:\s+(.*)")


@dataclass
class DiscoveredHost:
    host: str
    open_ports: list[int]
    asset_type: str
    vendor: str | None
    model: str | None
    protocol: str
    port: int | None
    notes: str


def _safe_network(cidr: str) -> ipaddress.IPv4Network:
    network = ipaddress.ip_network(cidr, strict=False)
    if network.version != 4:
        raise ValueError("Somente redes IPv4 sao suportadas para descoberta no momento.")
    if network.num_addresses > 1024:
        raise ValueError("A descoberta automatica esta limitada a redes com ate 1024 enderecos.")
    return network


def _parse_nmap_grepable_hosts(output: str) -> list[str]:
    hosts: list[str] = []
    for line in output.splitlines():
        match = NMAP_HOST_PATTERN.search(line)
        if match:
            hosts.append(match.group(1))
    return hosts


def _parse_nmap_grepable_ports(output: str) -> dict[str, list[int]]:
    ports_by_host: dict[str, list[int]] = {}
    for line in output.splitlines():
        match = NMAP_PORT_PATTERN.search(line)
        if not match:
            continue
        host, ports_blob = match.groups()
        open_ports: list[int] = []
        for item in ports_blob.split(","):
            pieces = item.strip().split("/")
            if len(pieces) < 2:
                continue
            port_text, state = pieces[0], pieces[1]
            if state != "open":
                continue
            try:
                open_ports.append(int(port_text))
            except ValueError:
                continue
        ports_by_host[host] = sorted(set(open_ports))
    return ports_by_host


def _run_nmap_host_discovery(cidr: str) -> tuple[list[str], dict[str, list[int]]] | None:
    if not shutil.which("nmap"):
        return None

    syn_ports = ",".join(str(port) for port in PRIMARY_SYN_PORTS)
    common_ports = ",".join(str(port) for port in COMMON_PORTS)

    host_scan = subprocess.run(
        ["nmap", "-n", "-sn", "-PE", f"-PS{syn_ports}", "-oG", "-", cidr],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    hosts = _parse_nmap_grepable_hosts(host_scan.stdout)
    if not hosts:
        return [], {}

    port_scan = subprocess.run(
        ["nmap", "-n", "-Pn", f"-p{common_ports}", "-oG", "-", *hosts],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return hosts, _parse_nmap_grepable_ports(port_scan.stdout)


async def _probe_port(host: str, port: int, timeout: float = 0.7) -> bool:
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


async def _fallback_discovery(cidr: str) -> tuple[list[str], dict[str, list[int]]]:
    network = _safe_network(cidr)
    host_list = [str(ip) for ip in network.hosts()]
    sem = asyncio.Semaphore(128)
    ports_by_host: dict[str, list[int]] = {}

    async def scan_host(host: str) -> None:
        async with sem:
            tasks = [asyncio.create_task(_probe_port(host, port)) for port in COMMON_PORTS]
            results = await asyncio.gather(*tasks)
            open_ports = [port for port, is_open in zip(COMMON_PORTS, results) if is_open]
            if open_ports:
                ports_by_host[host] = open_ports

    await asyncio.gather(*(scan_host(host) for host in host_list))
    return sorted(ports_by_host), ports_by_host


def _primary_port(protocol: str, ports: Iterable[int]) -> int | None:
    ports = set(ports)
    if protocol == "winbox" and 8291 in ports:
        return 8291
    if protocol == "rdp" and 3389 in ports:
        return 3389
    if protocol == "https" and 443 in ports:
        return 443
    if protocol == "http" and 80 in ports:
        return 80
    if protocol == "http" and 8080 in ports:
        return 8080
    if protocol == "rtsp" and 554 in ports:
        return 554
    if protocol == "ssh" and 22 in ports:
        return 22
    return next(iter(sorted(ports)), None)


def classify_host(host: str, open_ports: list[int]) -> DiscoveredHost:
    ports = set(open_ports)
    protocol = "http"
    asset_type = "device"
    vendor = None
    model = None
    notes_bits = [f"Portas abertas: {', '.join(str(port) for port in sorted(ports)) or 'nenhuma identificada'}."]

    if 8291 in ports or 8728 in ports or 8729 in ports:
        asset_type = "mikrotik"
        vendor = "MikroTik"
        protocol = "winbox" if 8291 in ports else "http"
    elif 8000 in ports or 554 in ports:
        asset_type = "dvr"
        vendor = "Hikvision" if 8000 in ports else None
        protocol = "https" if 443 in ports else "http"
        notes_bits.append("Equipamento com perfil de DVR/NVR identificado por RTSP/porta 8000.")
    elif 3389 in ports:
        asset_type = "machine"
        vendor = "Microsoft"
        model = "Windows Host"
        protocol = "rdp"
    elif 139 in ports or 445 in ports:
        asset_type = "machine"
        vendor = "Microsoft"
        model = "Windows Host"
        protocol = "http" if 80 in ports else "rdp"
    elif 53 in ports and (80 in ports or 443 in ports):
        asset_type = "router"
        model = "dnsmasq/http"
        protocol = "http" if 80 in ports else "https"
        notes_bits.append("Host com servico DNS e interface web.")
    elif 80 in ports or 443 in ports:
        asset_type = "device"
        protocol = "https" if 443 in ports else "http"
    elif 22 in ports:
        asset_type = "device"
        protocol = "ssh"
    else:
        asset_type = "unknown"
        protocol = "icmp"

    if host.endswith(".1") and asset_type not in {"dvr", "machine"}:
        asset_type = "mikrotik"
        vendor = vendor or "MikroTik"
        model = model or "Gateway"
        protocol = "winbox" if 8291 in ports else protocol
        notes_bits.append("IP .1 tratado como gateway principal da unidade.")

    name = {
        "mikrotik": f"MikroTik {host}",
        "dvr": f"DVR {host}",
        "machine": f"Host Windows {host}",
        "router": f"Roteador {host}",
        "unknown": f"Host Desconhecido {host}",
    }.get(asset_type, f"Dispositivo {host}")

    return DiscoveredHost(
        host=host,
        open_ports=sorted(ports),
        asset_type=asset_type,
        vendor=vendor,
        model=model,
        protocol=protocol,
        port=_primary_port(protocol, ports),
        notes=f"{name}. {' '.join(notes_bits)}",
    )


async def discover_network(cidr: str) -> tuple[list[DiscoveredHost], str]:
    discovered = await asyncio.to_thread(_run_nmap_host_discovery, cidr)
    scanner = "nmap"
    if discovered is None:
        scanner = "tcp-fallback"
        hosts, ports_by_host = await _fallback_discovery(cidr)
    else:
        hosts, ports_by_host = discovered

    results: list[DiscoveredHost] = []
    for host in hosts:
        results.append(classify_host(host, ports_by_host.get(host, [])))
    return sorted(results, key=lambda item: socket.inet_aton(item.host)), scanner
