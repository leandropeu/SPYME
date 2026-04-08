from __future__ import annotations

import argparse
import ipaddress
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "spygym.db"


def looks_like_cidr(value: str | None) -> bool:
    if not value:
        return False
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    return True


def derive_cidr(network_label: str | None, dvr_host: str | None) -> str | None:
    if looks_like_cidr(network_label):
        return network_label
    if not dvr_host:
        return None
    try:
        address = ipaddress.ip_address(dvr_host)
    except ValueError:
        return None
    if address.version != 4:
        return None
    network = ipaddress.ip_network(f"{address}/24", strict=False)
    return str(network)


def main() -> None:
    parser = argparse.ArgumentParser(description="Preenche defaults OpenVPN nas unidades ativas.")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--vpn-host", required=True)
    parser.add_argument("--vpn-port", type=int, default=1194)
    parser.add_argument("--vpn-type", default="openvpn")
    parser.add_argument("--adapter-prefix", default="SPYGYM")
    args = parser.parse_args()

    db_path = Path(args.db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {
            row["name"]
            for row in conn.execute("pragma table_info(units)")
        }
        base_columns = ["id", "code", "name"]
        optional_columns = [
            "network_label",
            "dvr_host",
            "vpn_type",
            "vpn_host",
            "vpn_port",
            "vpn_username",
            "vpn_network_cidr",
            "vpn_adapter_name",
        ]
        select_columns = base_columns + [
            column if column in columns else f"null as {column}"
            for column in optional_columns
        ]
        rows = conn.execute(
            f"""
            select {", ".join(select_columns)}
            from units
            where is_active = 1
            order by code
            """
        ).fetchall()

        updated = 0
        for row in rows:
            row_data = dict(row)
            code = (row["code"] or "").strip()
            values: dict[str, object] = {}

            if "vpn_type" in columns and not (row["vpn_type"] or "").strip():
                values["vpn_type"] = args.vpn_type
            if "vpn_host" in columns and not (row["vpn_host"] or "").strip():
                values["vpn_host"] = args.vpn_host
            if "vpn_port" in columns and not row["vpn_port"]:
                values["vpn_port"] = args.vpn_port
            if "vpn_username" in columns and not (row["vpn_username"] or "").strip():
                values["vpn_username"] = code or row["name"]

            derived_cidr = derive_cidr(row_data.get("network_label"), row_data.get("dvr_host"))
            if "vpn_network_cidr" in columns and not (row["vpn_network_cidr"] or "").strip() and derived_cidr:
                values["vpn_network_cidr"] = derived_cidr

            if "vpn_adapter_name" in columns and not (row["vpn_adapter_name"] or "").strip():
                values["vpn_adapter_name"] = f"{args.adapter_prefix}-{code or row['id']}"

            if not values:
                continue

            assignments = ", ".join(f"{column} = ?" for column in values)
            if "updated_at" in columns:
                assignments += ", updated_at = CURRENT_TIMESTAMP"
            params = list(values.values()) + [row["id"]]
            conn.execute(
                f"update units set {assignments} where id = ?",
                params,
            )
            updated += 1
            summary = ", ".join(f"{key}={value}" for key, value in values.items())
            print(f"[ok] unidade {code or row['id']}: {summary}")

        conn.commit()

    print(f"Atualizacao concluida. Unidades ajustadas: {updated}")


if __name__ == "__main__":
    main()
