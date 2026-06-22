from collections.abc import Callable
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.models.job import Job, JobStatus
from app.services.ansible_runner import AnsibleRunner
from app.services.config_writer import ConfigWriter
from app.services.job_store import JobStore

logger = logging.getLogger(__name__)

_DEPLOY_PLAYBOOKS = frozenset({
    "deploymentserver",
    "clustermanager",
    "shdeployer",
    "standalone",
    "sc4s_forwarder",
})


class JobManager:
    def __init__(self, store: JobStore | None = None) -> None:
        self._store = store or JobStore()
        self._output_cache: dict[str, list[str]] = {}

    def create_job(
        self,
        playbook: str,
        environment: str,
        git_pull_first: bool = False,
    ) -> Job:
        job_id = str(uuid4())
        job = Job(
            id=job_id,
            playbook=playbook,
            environment=environment,
            git_pull_first=git_pull_first,
            status=JobStatus.queued,
            created_at=datetime.now(UTC),
        )
        self._store.save_job(job)
        self._output_cache[job_id] = []
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._store.get_job(job_id)

    def get_job_output(self, job_id: str) -> list[str]:
        if job_id in self._output_cache:
            return list(self._output_cache[job_id])
        return self._store.get_log_lines(job_id)

    def list_jobs(self) -> list[Job]:
        return self._store.list_jobs()

    @staticmethod
    def _playbook_sequence(job: Job) -> list[str]:
        if job.git_pull_first and job.playbook != "git_client":
            return ["git_client", job.playbook]
        return [job.playbook]

    async def run_job(
        self,
        job_id: str,
        on_line: Callable[[list[str]], None] | None = None,
    ) -> Job:
        job = self._store.get_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        if job.status != JobStatus.queued:
            raise ValueError(f"Job {job_id} is not queued")

        job = job.model_copy(
            update={
                "status": JobStatus.running,
                "started_at": datetime.now(UTC),
            }
        )
        self._store.save_job(job)

        lines: list[str] = []
        self._output_cache[job_id] = lines
        playbooks = self._playbook_sequence(job)
        final_exit_code = 0

        def append_line(line: str) -> None:
            seq = len(lines)
            lines.append(line)
            self._store.append_log_line(job_id, seq, line)
            self._output_cache[job_id] = lines
            if on_line is not None:
                on_line(lines)

        try:
            for index, playbook in enumerate(playbooks):
                if len(playbooks) > 1:
                    if index > 0:
                        append_line("")
                    append_line(f"===== Starting playbook: {playbook} =====")

                runner = AnsibleRunner()
                async for line in runner.stream_playbook(playbook, job.environment):
                    append_line(line)

                exit_code = runner.exit_code if runner.exit_code is not None else -1
                final_exit_code = exit_code
                if exit_code != 0:
                    break
        except Exception:
            job = job.model_copy(
                update={
                    "status": JobStatus.failed,
                    "exit_code": -1,
                    "finished_at": datetime.now(UTC),
                }
            )
            self._store.save_job(job)
            raise

        if final_exit_code == 0:
            playbook_slug = job.playbook.removesuffix(".yml")
            if playbook_slug in _DEPLOY_PLAYBOOKS:
                try:
                    ConfigWriter().clear_target_removals(playbook_slug)
                    append_line(
                        f"Cleared pending app removals for {playbook_slug} in group_vars.",
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to clear pending app removals for %s: %s",
                        playbook_slug,
                        exc,
                    )
                    append_line(
                        f"Warning: could not clear pending app removals: {exc}",
                    )

        status = JobStatus.succeeded if final_exit_code == 0 else JobStatus.failed
        job = job.model_copy(
            update={
                "status": status,
                "exit_code": final_exit_code,
                "finished_at": datetime.now(UTC),
            }
        )
        self._store.save_job(job)
        return job
