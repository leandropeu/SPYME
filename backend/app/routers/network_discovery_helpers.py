from __future__ import annotations

from ..services.network_discovery import DiscoveredHost


def make_discovered_name(asset: DiscoveredHost) -> str:
    if asset.asset_type == "mikrotik":
        return f"MikroTik {asset.host}"
    if asset.asset_type == "dvr":
        return f"DVR {asset.host}"
    if asset.asset_type == "machine":
        return f"Host Windows {asset.host}"
    if asset.asset_type == "router":
        return f"Roteador {asset.host}"
    if asset.asset_type == "unknown":
        return f"Host Desconhecido {asset.host}"
    return f"Dispositivo {asset.host}"
