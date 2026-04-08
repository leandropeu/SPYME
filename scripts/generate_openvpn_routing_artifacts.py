from __future__ import annotations

import ipaddress
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"
OUTPUT_DIR = ROOT / "deploy" / "openvpn-routing"
CCD_DIR = OUTPUT_DIR / "ccd"


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def cidr_to_network_and_mask(cidr: str) -> tuple[str, str]:
    network = ipaddress.ip_network(cidr, strict=False)
    return str(network.network_address), str(network.netmask)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CCD_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            select code, name, vpn_username, vpn_network_cidr, vpn_host, coalesce(vpn_port, 1194)
            from units
            where is_active = 1
            order by code
            """
        ).fetchall()

    server_routes = []
    inventory = ["code,name,client_cn,vpn_network_cidr,route_network,route_mask,vpn_host,vpn_port,ccd_file"]

    for code, name, vpn_username, vpn_network_cidr, vpn_host, vpn_port in rows:
        client_cn = vpn_username or code or slugify(name)
        ccd_file = CCD_DIR / client_cn
        route_network = ""
        route_mask = ""
        ccd_content = [
            f"# Unidade: {name}",
            f"# Codigo: {code}",
            f"# CN do cliente: {client_cn}",
        ]
        if vpn_network_cidr:
            route_network, route_mask = cidr_to_network_and_mask(vpn_network_cidr)
            server_routes.append(f"route {route_network} {route_mask}")
            ccd_content.append(f"iroute {route_network} {route_mask}")
        else:
            ccd_content.append("# PREENCHER_REDE_DA_UNIDADE_AQUI")

        ccd_file.write_text("\n".join(ccd_content) + "\n", encoding="utf-8")
        inventory.append(
            f"{code},{name},{client_cn},{vpn_network_cidr or ''},{route_network},{route_mask},{vpn_host or ''},{vpn_port or 1194},{ccd_file.name}"
        )

    (OUTPUT_DIR / "server-routes.conf").write_text("\n".join(server_routes) + ("\n" if server_routes else ""), encoding="utf-8")
    (OUTPUT_DIR / "openvpn-routing-inventory.csv").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    print(f"Artefatos de rota gerados em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
