from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS synced_routes (
    komoot_tour_id  TEXT PRIMARY KEY,
    name            TEXT,
    sport_type      TEXT,
    distance_km     REAL,
    hammerhead_id   TEXT,
    synced_at       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS auth_cache (
    service     TEXT PRIMARY KEY,
    token       TEXT NOT NULL,
    user_id     TEXT,
    expires_at  TEXT
);
"""


def _connect() -> sqlite3.Connection:
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def get_synced_ids() -> set[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT komoot_tour_id FROM synced_routes WHERE status = 'success'"
        ).fetchall()
    return {r["komoot_tour_id"] for r in rows}


def is_synced(tour_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM synced_routes WHERE komoot_tour_id = ? AND status = 'success'",
            (tour_id,),
        ).fetchone()
    return row is not None


def mark_synced(
    tour_id: str,
    hammerhead_id: str | None,
    name: str = "",
    sport_type: str = "",
    distance_km: float = 0.0,
    status: str = "success",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """\
            INSERT INTO synced_routes
                (komoot_tour_id, name, sport_type, distance_km, hammerhead_id, synced_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(komoot_tour_id) DO UPDATE SET
                name          = excluded.name,
                sport_type    = excluded.sport_type,
                distance_km   = excluded.distance_km,
                hammerhead_id = excluded.hammerhead_id,
                synced_at     = excluded.synced_at,
                status        = excluded.status
            """,
            (tour_id, name, sport_type, distance_km, hammerhead_id, now, status),
        )


def get_stats() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM synced_routes").fetchone()[0]
        success = conn.execute(
            "SELECT COUNT(*) FROM synced_routes WHERE status = 'success'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM synced_routes WHERE status = 'failed'"
        ).fetchone()[0]
    return {"total": total, "success": success, "failed": failed}


def list_routes(limit: int = 50, offset: int = 0) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM synced_routes ORDER BY synced_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_route(tour_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM synced_routes WHERE komoot_tour_id = ?",
            (tour_id,),
        ).fetchone()
    return dict(row) if row else None


def update_route(tour_id: str, **fields: object) -> dict | None:
    allowed = {"name", "sport_type", "distance_km", "hammerhead_id", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_route(tour_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [tour_id]
    with _connect() as conn:
        conn.execute(
            f"UPDATE synced_routes SET {set_clause} WHERE komoot_tour_id = ?",
            values,
        )
    return get_route(tour_id)


def delete_route(tour_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM synced_routes WHERE komoot_tour_id = ?",
            (tour_id,),
        )
    return cur.rowcount > 0


# --- auth cache helpers ---


def get_cached_token(service: str) -> tuple[str, str | None] | None:
    """Return (token, user_id) if cached and not expired, else None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT token, user_id, expires_at FROM auth_cache WHERE service = ?",
            (service,),
        ).fetchone()
    if row is None:
        return None
    if row["expires_at"]:
        expires = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) >= expires:
            return None
    return row["token"], row["user_id"]


def save_token(
    service: str,
    token: str,
    user_id: str | None = None,
    expires_at: str | None = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """\
            INSERT INTO auth_cache (service, token, user_id, expires_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(service) DO UPDATE SET
                token      = excluded.token,
                user_id    = excluded.user_id,
                expires_at = excluded.expires_at
            """,
            (service, token, user_id, expires_at),
        )
