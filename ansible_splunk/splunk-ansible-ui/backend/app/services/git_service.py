from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import DEPLOYMENT_ROOT


@dataclass(frozen=True)
class GitCommitResult:
    success: bool
    commit_hash: str | None
    message: str


@dataclass(frozen=True)
class GitPushResult:
    success: bool
    message: str


class GitService:
    def __init__(self, deployment_root: Path | None = None) -> None:
        self.deployment_root = (deployment_root or DEPLOYMENT_ROOT).resolve()

    def _run_git(self, args: list[str], *, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.deployment_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout or "git command failed").strip()
            raise ValueError(detail)
        return result.stdout

    def _validate_repo(self) -> None:
        git_dir = self.deployment_root / ".git"
        if not git_dir.exists():
            raise ValueError(f"Not a git repository: {self.deployment_root}")

    def _validate_file_path(self, file_path: str) -> Path:
        if not file_path or file_path.startswith("/"):
            raise ValueError(f"Invalid file path: {file_path!r}")

        relative = Path(file_path)
        if ".." in relative.parts:
            raise ValueError(f"Invalid file path: {file_path!r}")

        resolved = (self.deployment_root / relative).resolve()
        if not resolved.is_relative_to(self.deployment_root):
            raise ValueError(f"Invalid file path: {file_path!r}")
        return resolved

    def _normalize_files(self, files: list[str]) -> list[str]:
        if not files:
            raise ValueError("At least one file is required")
        normalized: list[str] = []
        for file_path in files:
            resolved = self._validate_file_path(file_path)
            normalized.append(resolved.relative_to(self.deployment_root).as_posix())
        return normalized

    def get_status(self) -> list[str]:
        self._validate_repo()
        output = self._run_git(["status", "--porcelain"])
        files: list[str] = []

        for line in output.splitlines():
            if len(line) < 4:
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            files.append(path)

        return files

    def commit_changes(self, message: str, files: list[str]) -> GitCommitResult:
        self._validate_repo()
        if not message.strip():
            raise ValueError("Commit message cannot be empty")

        normalized_files = self._normalize_files(files)
        self._run_git(["add", "--", *normalized_files])
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(self.deployment_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if commit_result.returncode != 0:
            detail = (commit_result.stderr or commit_result.stdout or "").strip()
            if "nothing to commit" in detail.lower():
                return GitCommitResult(success=False, commit_hash=None, message=message)
            raise ValueError(detail or "git commit failed")

        commit_hash = self._run_git(["rev-parse", "HEAD"]).strip()
        return GitCommitResult(success=True, commit_hash=commit_hash, message=message)

    def push_changes(self) -> GitPushResult:
        self._validate_repo()
        result = subprocess.run(
            ["git", "push"],
            cwd=str(self.deployment_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            output = (result.stdout or result.stderr or "").strip()
            return GitPushResult(success=True, message=output)
        error = (result.stderr or result.stdout or "git push failed").strip()
        return GitPushResult(success=False, message=error)
