from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import subprocess

from app.config import DEPLOYMENT_ROOT
from app.services.git_service import GitService

router = APIRouter()
_service = GitService()


class GitStatusResponse(BaseModel):
    files: list[str]


class GitPullResult(BaseModel):
    success: bool
    message: str


def _handle_git_errors(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/git/status", response_model=GitStatusResponse)
def get_git_status() -> GitStatusResponse:
    try:
        return GitStatusResponse(files=_service.get_status())
    except ValueError as exc:
        _handle_git_errors(exc)
        raise


@router.get("/git/pull", response_model=GitPullResult)
def pull_git_changes() -> GitPullResult:
    try:
        deployment_root = DEPLOYMENT_ROOT.resolve()
        if not (deployment_root / ".git").exists():
            raise ValueError(f"Not a git repository: {deployment_root}")

        result = subprocess.run(
            ["git", "pull"],
            cwd=str(deployment_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            output = (result.stdout or result.stderr or "").strip()
            return GitPullResult(success=True, message=output)
        error = (result.stderr or result.stdout or "git pull failed").strip()
        return GitPullResult(success=False, message=error)
    except ValueError as exc:
        _handle_git_errors(exc)
        raise
