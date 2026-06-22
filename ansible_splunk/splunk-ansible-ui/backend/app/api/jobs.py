import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.config import ALLOWED_ENVIRONMENTS, ALLOWED_PLAYBOOKS
from app.models.job import Job, JobCreate, JobOutputResponse, JobStatus
from app.services.job_manager import JobManager

router = APIRouter()

_INVALID_JOB_ERROR = "Playbook or environment is not allowed"


class JobCreatedResponse(BaseModel):
    id: str
    status: JobStatus


class StreamingJobManager(JobManager):
    async def run_job(self, job_id: str) -> Job:
        def on_line(lines: list[str]) -> None:
            self._output_cache[job_id] = list(lines)

        return await super().run_job(job_id, on_line=on_line)


job_manager = StreamingJobManager()


def _validate_job_request(playbook: str, environment: str) -> None:
    if playbook not in ALLOWED_PLAYBOOKS or environment not in ALLOWED_ENVIRONMENTS:
        raise HTTPException(status_code=400, detail=_INVALID_JOB_ERROR)


@router.post("/jobs", status_code=202, response_model=JobCreatedResponse)
async def create_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
) -> JobCreatedResponse:
    _validate_job_request(body.playbook, body.environment)
    job = job_manager.create_job(
        body.playbook,
        body.environment,
        git_pull_first=body.git_pull_first,
    )
    background_tasks.add_task(job_manager.run_job, job.id)
    return JobCreatedResponse(id=job.id, status=job.status)


@router.get("/jobs", response_model=list[Job])
def list_jobs() -> list[Job]:
    return job_manager.list_jobs()


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.get("/jobs/{job_id}/output", response_model=JobOutputResponse)
def get_job_output(job_id: str) -> JobOutputResponse:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobOutputResponse(job_id=job_id, lines=job_manager.get_job_output(job_id))


@router.websocket("/jobs/{job_id}/stream")
async def stream_job(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    job = job_manager.get_job(job_id)
    if job is None:
        await websocket.close(code=1008, reason="Job not found")
        return

    sent = 0
    try:
        while True:
            job = job_manager.get_job(job_id)
            if job is None:
                break

            lines = job_manager.get_job_output(job_id)
            while sent < len(lines):
                await websocket.send_json({"type": "log", "line": lines[sent]})
                sent += 1

            if job.status in (JobStatus.succeeded, JobStatus.failed):
                await websocket.send_json(
                    {
                        "status": job.status.value,
                        "exit_code": job.exit_code,
                    }
                )
                await websocket.close()
                return

            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        return
