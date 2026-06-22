import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATABASE_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SettingsStore:
    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = (database_path or DATABASE_PATH).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return row["value"]

    def set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, self._now()),
            )

    def get_all(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value FROM settings ORDER BY key"
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}
