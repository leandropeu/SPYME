from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "backend" / "data" / "spygym.db"


def fetch_scalar(cursor: sqlite3.Cursor, query: str) -> int:
    return int(cursor.execute(query).fetchone()[0])


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        tables = [
            row[0]
            for row in cursor.execute(
                "select name from sqlite_master where type = 'table' and name not like 'sqlite_%' order by name"
            ).fetchall()
        ]

        counts = {
            table: fetch_scalar(cursor, f"select count(*) from {table}")
            for table in tables
        }

        integrity = {
            "duplicate_user_email": fetch_scalar(
                cursor,
                "select count(*) from (select email from users group by email having count(*) > 1)",
            ),
            "duplicate_unit_code": fetch_scalar(
                cursor,
                "select count(*) from (select code from units group by code having count(*) > 1)",
            ),
            "duplicate_dvr_per_unit": fetch_scalar(
                cursor,
                "select count(*) from (select unit_id, name from dvrs group by unit_id, name having count(*) > 1)",
            ),
            "duplicate_camera_channel": fetch_scalar(
                cursor,
                "select count(*) from (select dvr_id, channel_number from cameras where dvr_id is not null group by dvr_id, channel_number having count(*) > 1)",
            ),
            "orphan_auth_tokens": fetch_scalar(
                cursor,
                "select count(*) from auth_tokens t left join users u on u.id = t.user_id where u.id is null",
            ),
            "orphan_dvrs": fetch_scalar(
                cursor,
                "select count(*) from dvrs d left join units u on u.id = d.unit_id where u.id is null",
            ),
            "orphan_cameras_unit": fetch_scalar(
                cursor,
                "select count(*) from cameras c left join units u on u.id = c.unit_id where u.id is null",
            ),
            "orphan_cameras_dvr": fetch_scalar(
                cursor,
                "select count(*) from cameras c left join dvrs d on d.id = c.dvr_id where c.dvr_id is not null and d.id is null",
            ),
            "inactive_users": fetch_scalar(cursor, "select count(*) from users where is_active = 0"),
            "active_tokens": fetch_scalar(
                cursor,
                "select count(*) from auth_tokens where revoked_at is null and expires_at > datetime('now')",
            ),
        }

        samples = {
            "users": cursor.execute(
                "select id, full_name, email, role, is_active, last_login_at from users order by id limit 10"
            ).fetchall(),
            "backups": cursor.execute(
                "select id, file_name, status, started_at, completed_at from backup_records order by id desc limit 5"
            ).fetchall(),
        }

    report = {
        "database": str(DB_PATH),
        "tables": tables,
        "counts": counts,
        "integrity": integrity,
        "samples": samples,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
