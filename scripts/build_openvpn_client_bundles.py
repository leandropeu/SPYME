from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"
TEMPLATE_DIR = ROOT / "deploy" / "openvpn-units"
OUTPUT_DIR = ROOT / "deploy" / "openvpn-bundles"

SERVER_PKI = Path("/etc/openvpn/server/spygym/pki")
EASYRSA_PKI = Path("/etc/openvpn/easy-rsa/pki")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            select code, name, coalesce(nullif(vpn_username, ''), code) as client_cn
            from units
            where is_active = 1
            order by code
            """
        ).fetchall()

    ca = (SERVER_PKI / "ca.crt").read_text(encoding="utf-8")
    tls_crypt = (SERVER_PKI / "tls-crypt.key").read_text(encoding="utf-8")

    for code, name, client_cn in rows:
        candidates = sorted(TEMPLATE_DIR.glob(f"{code}-*.ovpn"))
        if not candidates:
            continue
        template_path = candidates[0]
        content = template_path.read_text(encoding="utf-8")

        cert = (EASYRSA_PKI / "issued" / f"{client_cn}.crt").read_text(encoding="utf-8")
        key = (EASYRSA_PKI / "private" / f"{client_cn}.key").read_text(encoding="utf-8")

        content = content.replace("COLE_A_CA_AQUI", ca.strip())
        content = content.replace("COLE_O_CERTIFICADO_DO_CLIENTE_AQUI", cert.strip())
        content = content.replace("COLE_A_CHAVE_DO_CLIENTE_AQUI", key.strip())
        content = content.replace("COLE_A_CHAVE_TLS_CRYPT_AQUI", tls_crypt.strip())

        output_path = OUTPUT_DIR / template_path.name
        output_path.write_text(content, encoding="utf-8")
        print(f"Bundle gerado: {output_path}")


if __name__ == "__main__":
    main()
