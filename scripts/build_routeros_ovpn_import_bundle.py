from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"
BUNDLES_DIR = ROOT / "deploy" / "openvpn-bundles"
OUTPUT_DIR = ROOT / "deploy" / "openvpn-routeros"


def insert_key_direction(content: str) -> str:
    if "key-direction 1" in content:
        return content
    marker = "<tls-crypt>"
    if marker not in content:
        return content
    return content.replace(marker, "key-direction 1\n\n<tls-crypt>", 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera perfis .ovpn compatíveis com importação no RouterOS.")
    parser.add_argument("--unit-code", default=None, help="Filtra por código de unidade, ex.: 07")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            select code, name
            from units
            where is_active = 1
              and (? is null or code = ?)
            order by code
            """,
            (args.unit_code, args.unit_code),
        ).fetchall()

    generated = 0
    for code, name in rows:
        candidates = sorted(BUNDLES_DIR.glob(f"{code}-*.ovpn"))
        if not candidates:
            continue
        source_path = candidates[0]
        content = source_path.read_text(encoding="utf-8")
        content = insert_key_direction(content)
        header = (
            f"# Perfil RouterOS para unidade {code} - {name}\n"
            "# Recomendado para RouterOS 7.17+ com importacao via /interface/ovpn-client/import-ovpn-configuration\n"
            "# Use um usuario/senha dummy no import se o RouterOS exigir; a autenticacao principal esta no certificado.\n\n"
        )
        output_path = OUTPUT_DIR / source_path.name
        output_path.write_text(header + content, encoding="utf-8")
        generated += 1
        print(f"RouterOS bundle gerado: {output_path}")

    print(f"Perfis RouterOS gerados: {generated}")


if __name__ == "__main__":
    main()
