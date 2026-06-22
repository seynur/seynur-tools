import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import DATABASE_PATH
from app.models.job import Job, JobStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    playbook TEXT NOT NULL,
    environment TEXT NOT NULL,
    git_pull_first INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    exit_code INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS job_log_lines (
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    line TEXT NOT NULL,
    PRIMARY KEY (job_id, seq),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
"""


class JobStore:
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
    def _dt_to_str(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _str_to_dt(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            playbook=row["playbook"],
            environment=row["environment"],
            git_pull_first=bool(row["git_pull_first"]),
            status=JobStatus(row["status"]),
            exit_code=row["exit_code"],
            created_at=JobStore._str_to_dt(row["created_at"]),
            started_at=JobStore._str_to_dt(row["started_at"]),
            finished_at=JobStore._str_to_dt(row["finished_at"]),
        )

    def save_job(self, job: Job) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, playbook, environment, git_pull_first,
                    status, exit_code, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    exit_code = excluded.exit_code,
                    started_at = excluded.started_at,
                    finished_at = excluded.finished_at
                """,
                (
                    job.id,
                    job.playbook,
                    job.environment,
                    int(job.git_pull_first),
                    job.status.value,
                    job.exit_code,
                    self._dt_to_str(job.created_at),
                    self._dt_to_str(job.started_at),
                    self._dt_to_str(job.finished_at),
                ),
            )

    def get_job(self, job_id: str) -> Job | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def list_jobs(self) -> list[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def append_log_line(self, job_id: str, seq: int, line: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO job_log_lines (job_id, seq, line) VALUES (?, ?, ?)",
                (job_id, seq, line),
            )

    def get_log_lines(self, job_id: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT line FROM job_log_lines WHERE job_id = ? ORDER BY seq",
                (job_id,),
            ).fetchall()
        return [row["line"] for row in rows]
