import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

from app.config import DEPLOYMENT_ROOT, get_splunkapps_path
from app.services.config_reader import validate_safe_name


class AnsibleRunner:
    def __init__(self, deployment_root: Path | None = None) -> None:
        self.deployment_root = deployment_root or DEPLOYMENT_ROOT
        self.exit_code: int | None = None

    def build_command(self, playbook: str, environment: str) -> list[str]:
        playbook_slug = playbook.removesuffix(".yml")
        validate_safe_name(playbook_slug, "playbook")
        validate_safe_name(environment, "environment")

        inventory_path = (self.deployment_root / "inventory" / environment).resolve()
        inventory_root = (self.deployment_root / "inventory").resolve()
        if not inventory_path.is_relative_to(inventory_root):
            raise ValueError(f"Invalid environment: {environment!r}")

        playbook_path = (self.deployment_root / "playbooks" / f"{playbook_slug}.yml").resolve()
        playbooks_root = (self.deployment_root / "playbooks").resolve()
        if not playbook_path.is_relative_to(playbooks_root):
            raise ValueError(f"Invalid playbook: {playbook!r}")

        return [
            "ansible-playbook",
            "-i",
            f"inventory/{environment}",
            f"playbooks/{playbook_slug}.yml",
        ]

    def build_subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["SPLUNKAPPS_PATH"] = get_splunkapps_path()
        return env

    async def stream_playbook(
        self,
        playbook: str,
        environment: str,
    ) -> AsyncIterator[str]:
        self.exit_code = None
        command = self.build_command(playbook, environment)

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(self.deployment_root),
            env=self.build_subprocess_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        if process.stdout is None:
            raise RuntimeError("Failed to capture ansible-playbook stdout")

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode(errors="replace").rstrip("\r\n")
        finally:
            self.exit_code = await process.wait()
