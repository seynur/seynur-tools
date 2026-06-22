from dataclasses import dataclass
from pathlib import Path
import re

import yaml

from app.config import ALLOWED_ENVIRONMENTS, ALLOWED_PLAYBOOKS, DEPLOYMENT_ROOT
from app.models.environment import Environment
from app.models.target import Target, TargetApp, TargetsResponse

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_safe_name(value: str, field: str) -> str:
    if not _SAFE_NAME_RE.fullmatch(value):
        raise ValueError(
            f"Invalid {field}: must contain only letters, numbers, hyphens, and underscores"
        )
    return value


TARGET_DISPLAY_NAMES: dict[str, str] = {
    "git_client": "Git Client",
    "deploymentserver": "Deployment Server",
    "clustermanager": "Cluster Manager",
    "shdeployer": "SHC Deployer",
    "standalone": "Standalone Search Head",
    "sc4s_forwarder": "SC4S Forwarder",
}


def target_display_name(target_id: str) -> str:
    return TARGET_DISPLAY_NAMES.get(target_id, target_id)


@dataclass(frozen=True)
class _TargetSpec:
    id: str
    playbook: str
    group: str
    group_vars_file: str | None
    dest_key: str | None
    apps_key: str | None


_TARGET_SPECS: tuple[_TargetSpec, ...] = (
    _TargetSpec("git_client", "git_client.yml", "git_client", None, None, None),
    _TargetSpec(
        "deploymentserver",
        "deploymentserver.yml",
        "deploymentserver",
        "deploymentserver.yml",
        "splunk_dest",
        None,
    ),
    _TargetSpec(
        "clustermanager",
        "clustermanager.yml",
        "clustermanager",
        "clustermanager.yml",
        "splunk_dest",
        None,
    ),
    _TargetSpec(
        "shdeployer",
        "shdeployer.yml",
        "shdeployer",
        "shdeployer.yml",
        "splunk_dest",
        None,
    ),
    _TargetSpec(
        "standalone",
        "standalone.yml",
        "standalone",
        "standalone.yml",
        "splunk_dest",
        None,
    ),
    _TargetSpec(
        "sc4s_forwarder",
        "sc4s_forwarder.yml",
        "sc4s_forwarder",
        "sc4s_forwarder.yml",
        "sc4s_splunk_dest",
        None,
    ),
)


class ConfigReader:
    def __init__(self, deployment_root: Path | None = None) -> None:
        self.deployment_root = deployment_root or DEPLOYMENT_ROOT
        self.inventory_dir = self.deployment_root / "inventory"
        self.group_vars_dir = self.inventory_dir / "group_vars"

    def read_environments(self) -> list[Environment]:
        environments: list[Environment] = []
        for inventory_file in sorted(self.inventory_dir.iterdir()):
            if not inventory_file.is_file():
                continue
            name = inventory_file.name
            environments.append(
                Environment(
                    name=name,
                    inventory_file=f"inventory/{name}",
                    runnable=name in ALLOWED_ENVIRONMENTS,
                )
            )
        return environments

    def read_git_path(self) -> str:
        import os
        data = self._load_yaml(self.group_vars_dir / "all.yml")
        git_path = data.get("git_splunkapps_path")
        if not git_path:
            raise ValueError("git_splunkapps_path not found in inventory/group_vars/all.yml")
        git_path = str(git_path)
        if "lookup('env'" in git_path:
            env_path = os.environ.get("SPLUNKAPPS_PATH")
            if env_path:
                return env_path
            return str((self.deployment_root / "apps").resolve())
        return git_path

    def read_targets(self, environment: str) -> TargetsResponse:
        validate_safe_name(environment, "environment")
        inventory_path = (self.inventory_dir / environment).resolve()
        inventory_root = self.inventory_dir.resolve()
        if not inventory_path.is_relative_to(inventory_root):
            raise ValueError(f"Invalid environment: {environment!r}")
        if not inventory_path.is_file():
            raise FileNotFoundError(f"Inventory not found: inventory/{environment}")

        groups = self._parse_inventory(inventory_path)
        git_path = self.read_git_path()

        targets: list[Target] = []
        for spec in _TARGET_SPECS:
            targets.append(self._build_target(spec, groups))

        return TargetsResponse(
            environment=environment,
            git_path=git_path,
            targets=targets,
        )

    def _build_target(self, spec: _TargetSpec, groups: dict[str, list[str]]) -> Target:
        hosts = groups.get(spec.group, [])

        if spec.group_vars_file is None:
            destination = None
            apps: list[TargetApp] = []
            apps_to_remove: list[TargetApp] = []
        else:
            data = self._load_yaml(self.group_vars_dir / spec.group_vars_file)
            destination = data.get(spec.dest_key)
            if destination is not None:
                destination = str(destination)
            apps = self._read_apps(data, spec.apps_key)
            apps_to_remove = self._read_apps_to_remove(data)

        return Target(
            id=spec.id,
            playbook=spec.playbook,
            group=spec.group,
            hosts=hosts,
            destination=destination,
            apps=apps,
            apps_to_remove=apps_to_remove,
            runnable=spec.id in ALLOWED_PLAYBOOKS,
            display_name=target_display_name(spec.id),
        )

    def _parse_inventory(self, path: Path) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        current_group: str | None = None

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                if section.endswith(":children"):
                    current_group = None
                    continue
                current_group = section
                groups.setdefault(current_group, [])
                continue

            if current_group is None:
                continue

            host = line.split()[0]
            groups[current_group].append(host)

        return groups

    @staticmethod
    def _read_apps(data: dict, legacy_apps_key: str | None) -> list[TargetApp]:
        raw_apps = data.get("apps")
        if raw_apps is None and legacy_apps_key:
            raw_apps = data.get(legacy_apps_key, [])
        if not raw_apps:
            return []
        return ConfigReader._parse_apps(raw_apps)

    @staticmethod
    def _read_apps_to_remove(data: dict) -> list[TargetApp]:
        raw_apps = data.get("splunk_apps_to_remove", [])
        if not raw_apps:
            return []
        return ConfigReader._parse_apps(raw_apps)

    @staticmethod
    def _parse_apps(raw_apps: list) -> list[TargetApp]:
        apps: list[TargetApp] = []
        for item in raw_apps:
            if isinstance(item, dict):
                name = item.get("name")
                if not name:
                    continue
                apps.append(TargetApp(name=str(name)))
            else:
                apps.append(TargetApp(name=str(item)))
        return apps

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data if isinstance(data, dict) else {}
