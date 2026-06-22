from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobCreate(BaseModel):
    playbook: str
    environment: str
    git_pull_first: bool = False


class Job(BaseModel):
    id: str
    playbook: str
    environment: str
    git_pull_first: bool = False
    status: JobStatus
    exit_code: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobStreamMessage(BaseModel):
    type: Literal["log", "complete"]
    line: str | None = None
    status: JobStatus | None = None
    exit_code: int | None = None


class JobOutputResponse(BaseModel):
    job_id: str
    lines: list[str]
