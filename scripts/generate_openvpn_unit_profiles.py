from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"
OUTPUT_DIR = ROOT / "deploy" / "openvpn-units"
TEMPLATE_PATH = ROOT / "deploy" / "openvpn-client-unit.ovpn.example"


def slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            select id, code, name, vpn_type, vpn_host, coalesce(vpn_port, 1194), vpn_username, vpn_network_cidr
            from units
            where is_active = 1
            order by code
            """
        ).fetchall()

    inventory_lines = ["code,name,vpn_type,vpn_host,vpn_port,vpn_username,vpn_network_cidr,file_name"]

    for unit_id, code, name, vpn_type, vpn_host, vpn_port, vpn_username, vpn_network_cidr in rows:
        file_name = f"{code}-{slugify(name)}.ovpn"
        content = template.replace("VPN_HOST", vpn_host or "PREENCHER_HOST_VPN")
        content = content.replace("VPN_PORT", str(vpn_port or 1194))
        content += f"\n# Unidade: {name}\n"
        content += f"# Codigo: {code}\n"
        content += f"# Tipo de VPN cadastrado: {vpn_type or 'openvpn'}\n"
        content += f"# Usuario sugerido: {vpn_username or 'PREENCHER_USUARIO'}\n"
        content += f"# Rede remota esperada: {vpn_network_cidr or 'PREENCHER_REDE_CIDR'}\n"
        (OUTPUT_DIR / file_name).write_text(content, encoding="utf-8")
        inventory_lines.append(
            f"{code},{name},{vpn_type or 'openvpn'},{vpn_host or ''},{vpn_port or 1194},{vpn_username or ''},{vpn_network_cidr or ''},{file_name}"
        )

    (OUTPUT_DIR / "openvpn-units-inventory.csv").write_text("\n".join(inventory_lines), encoding="utf-8")
    print(f"Perfis gerados em: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
