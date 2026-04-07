from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zipfile import ZipFile


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "backend" / "data" / "spygym.db"
XLSX_PATH = ROOT_DIR / "base de dados unidades.xlsx"

NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

CITY_BY_REGION = {
    "CAR": "Carapicuiba",
    "CGR": "Campo Grande",
    "CUR": "Curitiba",
    "DIA": "Diadema",
    "EXT": "Extrema",
    "FRA": "Franca",
    "GOI": "Goiania",
    "GUA": "Guarulhos",
    "IND": "Indaiatuba",
    "LPA": "Laranjal Paulista",
    "MAU": "Maua",
    "MGC": "Mogi das Cruzes",
    "PGR": "Praia Grande",
    "POA": "Poa",
    "RIP": "Ribeirao Pires",
    "SAN": "Santo Andre",
    "SBC": "Sao Bernardo do Campo",
    "SCS": "Sao Caetano do Sul",
    "SPA": "Sao Paulo",
    "SVI": "Sao Vicente",
}

CITY_BY_NAME = {
    "Carapicuíba": "Carapicuiba",
    "Curitiba": "Curitiba",
    "Diadema": "Diadema",
    "Extrema": "Extrema",
    "Franca": "Franca",
    "Indaiatuba": "Indaiatuba",
    "Laranjal Paulista": "Laranjal Paulista",
    "Mogi das Cruzes": "Mogi das Cruzes",
    "Poa": "Poa",
    "Sao Vicente": "Sao Vicente",
    "São Vicente": "Sao Vicente",
}


@dataclass
class UnitRow:
    name: str
    code: str
    city: str | None
    state: str | None
    address: str | None
    notes: str | None


def read_shared_strings(zip_file: ZipFile) -> list[str]:
    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("x:si", NS):
        strings.append("".join(item.itertext()).strip())
    return strings


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.replace("\xa0", " ").split())
    return cleaned or None


def normalize_code(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        raise ValueError(f"Codigo invalido: {value!r}")
    number = int(digits)
    return str(number).zfill(2) if number < 100 else str(number)


def infer_city(name: str, region: str | None, state: str | None) -> str | None:
    if name in CITY_BY_NAME:
        return CITY_BY_NAME[name]
    if state == "GO" and region == "GUA":
        return "Goiania"
    return CITY_BY_REGION.get(region or "")


def parse_rows() -> list[UnitRow]:
    with ZipFile(XLSX_PATH) as zip_file:
        shared = read_shared_strings(zip_file)
        sheet = ET.fromstring(zip_file.read("xl/worksheets/sheet1.xml"))

    rows: list[UnitRow] = []
    for row in sheet.findall("x:sheetData/x:row", NS):
        values: dict[str, str] = {}
        for cell in row.findall("x:c", NS):
            ref = cell.attrib.get("r", "")
            column = "".join(ch for ch in ref if ch.isalpha())
            raw = cell.findtext("x:v", default="", namespaces=NS)
            if cell.attrib.get("t") == "s":
                value = shared[int(raw)]
            else:
                value = raw
            values[column] = value

        name = normalize_text(values.get("A"))
        code = normalize_text(values.get("B"))
        region = normalize_text(values.get("C"))
        state = normalize_text(values.get("D"))
        address = normalize_text(values.get("H"))
        if not name or not code:
            continue

        normalized_code = normalize_code(code)
        city = infer_city(name, region, state)

        note_parts = [f"Importado da planilha base de dados unidades em {date.today().isoformat()}."]
        if region:
            note_parts.append(f"Sigla operacional: {region}.")
        if not address:
            note_parts.append("Endereco nao informado na planilha original.")

        rows.append(
            UnitRow(
                name=name,
                code=normalized_code,
                city=city,
                state=state,
                address=address,
                notes=" ".join(note_parts),
            )
        )

    return rows


def merge_notes(existing: str | None, imported: str | None) -> str | None:
    existing = normalize_text(existing)
    imported = normalize_text(imported)
    if existing and imported:
        if imported in existing:
            return existing
        return f"{existing} {imported}"
    return existing or imported


def main() -> None:
    rows = parse_rows()
    summary = {"inserted": 0, "updated": 0, "unchanged": 0, "total_rows": len(rows)}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        existing_by_code = {
            row["code"]: row
            for row in cursor.execute(
                """
                select id, name, code, city, state, address, manager_name, manager_phone,
                       network_label, notes, is_active
                from units
                """
            ).fetchall()
        }

        for item in rows:
            existing = existing_by_code.get(item.code)
            if existing:
                next_name = item.name
                next_city = item.city or existing["city"]
                next_state = item.state or existing["state"]
                next_address = item.address or existing["address"]
                next_notes = merge_notes(existing["notes"], item.notes)
                changed = any(
                    [
                        next_name != existing["name"],
                        next_city != existing["city"],
                        next_state != existing["state"],
                        next_address != existing["address"],
                        next_notes != existing["notes"],
                        int(existing["is_active"]) != 1,
                    ]
                )

                if changed:
                    cursor.execute(
                        """
                        update units
                           set name = ?,
                               city = ?,
                               state = ?,
                               address = ?,
                               notes = ?,
                               is_active = 1
                         where id = ?
                        """,
                        (next_name, next_city, next_state, next_address, next_notes, existing["id"]),
                    )
                    summary["updated"] += 1
                else:
                    summary["unchanged"] += 1
                continue

            cursor.execute(
                """
                insert into units (
                    name, code, city, state, address, manager_name, manager_phone,
                    network_label, notes, is_active, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (item.name, item.code, item.city, item.state, item.address, None, None, None, item.notes, 1),
            )
            summary["inserted"] += 1

        conn.commit()

        total_units = cursor.execute("select count(*) from units").fetchone()[0]
        print({**summary, "total_units_after": total_units})


if __name__ == "__main__":
    main()
