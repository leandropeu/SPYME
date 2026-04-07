from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path(r"C:\Users\Admin\X\SPYGYM\backend\data\spygym.db")

USER_PATTERNS = ("teste", "test", "smoke", "demo", "mock", "example")
DVR_PATTERNS = ("smoke", "teste", "test", "demo", "mock")
CLOUD_PATTERNS = ("smoke", "teste", "test", "demo", "mock")
def like_clause(column: str, patterns: tuple[str, ...]) -> tuple[str, list[str]]:
    clauses = [f"lower({column}) like ?" for _ in patterns]
    values = [f"%{pattern}%" for pattern in patterns]
    return " OR ".join(clauses), values


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    deleted: dict[str, int] = {}

    user_name_clause, user_name_values = like_clause("full_name", USER_PATTERNS)
    user_email_clause, user_email_values = like_clause("email", USER_PATTERNS)
    user_ids = [
        row[0]
        for row in cur.execute(
            f"""
            select id
            from users
            where lower(email) <> 'admin@spygym.local'
              and (({user_name_clause}) or ({user_email_clause}))
            """,
            [*user_name_values, *user_email_values],
        ).fetchall()
    ]
    if user_ids:
        cur.executemany("delete from auth_tokens where user_id = ?", [(user_id,) for user_id in user_ids])
        cur.executemany("delete from users where id = ?", [(user_id,) for user_id in user_ids])
    deleted["users"] = len(user_ids)

    dvr_clause, dvr_values = like_clause("name", DVR_PATTERNS)
    dvr_ids = [row[0] for row in cur.execute(f"select id from dvrs where {dvr_clause}", dvr_values).fetchall()]
    if dvr_ids:
        cur.executemany("delete from cameras where dvr_id = ?", [(dvr_id,) for dvr_id in dvr_ids])
        cur.executemany("delete from dvrs where id = ?", [(dvr_id,) for dvr_id in dvr_ids])
    deleted["dvrs"] = len(dvr_ids)

    camera_clause, camera_values = like_clause("name", DVR_PATTERNS)
    deleted["orphan_cameras"] = cur.execute(f"delete from cameras where {camera_clause}", camera_values).rowcount

    cloud_name_clause, cloud_name_values = like_clause("name", CLOUD_PATTERNS)
    cloud_email_clause, cloud_email_values = like_clause("email", CLOUD_PATTERNS)
    deleted["cloud_accounts"] = cur.execute(
        f"""
        delete from cloud_accounts
        where (({cloud_name_clause}) or ({cloud_email_clause}))
          and id not in (select distinct coalesce(cloud_account_id, -1) from dvrs where cloud_account_id is not null)
        """,
        [*cloud_name_values, *cloud_email_values],
    ).rowcount

    deleted["events"] = cur.execute("delete from monitoring_events").rowcount

    conn.commit()
    conn.close()
    print(deleted)


if __name__ == "__main__":
    main()
