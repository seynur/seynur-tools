from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from app.config import DEPLOYMENT_ROOT, get_splunkapps_path
from app.models.target import TargetApp
from app.services.config_reader import validate_safe_name
from app.services.git_service import GitService

_WRITABLE_TARGETS: dict[str, tuple[str, str]] = {
    "deploymentserver": ("deploymentserver.yml", "splunk_dest"),
    "clustermanager": ("clustermanager.yml", "splunk_dest"),
    "shdeployer": ("shdeployer.yml", "splunk_dest"),
    "standalone": ("standalone.yml", "splunk_dest"),
    "sc4s_forwarder": ("sc4s_forwarder.yml", "sc4s_splunk_dest"),
}


@dataclass(frozen=True)
class TargetConfig:
    target_id: str
    group: str
    destination: str
    apps: list[TargetApp]
    apps_to_remove: list[TargetApp]


class ConfigWriter:
    def __init__(self, deployment_root: Path | None = None) -> None:
        self.deployment_root = deployment_root or DEPLOYMENT_ROOT
        self.group_vars_dir = self.deployment_root / "inventory" / "group_vars"

    @staticmethod
    def _yaml_rt() -> YAML:
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        return yaml

    def _target_spec(self, target_id: str) -> tuple[str, str]:
        validate_safe_name(target_id, "target")
        spec = _WRITABLE_TARGETS.get(target_id)
        if spec is None:
            raise ValueError(f"Target has no editable configuration: {target_id}")
        return spec

    def _group_vars_path(self, target_id: str) -> Path:
        group_vars_file, _ = self._target_spec(target_id)
        return self.group_vars_dir / group_vars_file

    def group_vars_relative_path(self, target_id: str) -> str:
        group_vars_file, _ = self._target_spec(target_id)
        return f"inventory/group_vars/{group_vars_file}"

    def _resolve_splunkapps_path(self) -> Path:
        configured = get_splunkapps_path()
        if configured.strip():
            return Path(configured).expanduser().resolve()
        return (self.deployment_root / "apps").resolve()

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
    def _apps_to_yaml(apps: list[TargetApp]) -> list[dict[str, str]]:
        return [{"name": app.name} for app in apps]

    def _load_group_vars(self, target_id: str) -> tuple[Path, dict, YAML]:
        path = self._group_vars_path(target_id)
        if not path.is_file():
            group_vars_file, _ = self._target_spec(target_id)
            raise FileNotFoundError(f"group_vars file not found: {group_vars_file}")

        yaml = self._yaml_rt()
        with path.open(encoding="utf-8") as handle:
            data = yaml.load(handle)

        if not isinstance(data, dict):
            group_vars_file, _ = self._target_spec(target_id)
            raise ValueError(f"Invalid group_vars file: {group_vars_file}")

        return path, data, yaml

    def _save_group_vars(self, path: Path, data: dict, yaml: YAML) -> None:
        with path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle)

    def _commit_and_push(self, target_id: str, message: str) -> None:
        git = GitService(self.deployment_root)
        relative_path = self.group_vars_relative_path(target_id)
        commit_result = git.commit_changes(message, [relative_path])
        if not commit_result.success:
            return

        push_result = git.push_changes()
        if not push_result.success:
            raise ValueError(push_result.message)

    def validate_apps_exist(self, apps: list[TargetApp]) -> None:
        if not apps:
            raise ValueError("At least one app is required")

        splunkapps_path = self._resolve_splunkapps_path()
        missing: list[str] = []

        for app in apps:
            validate_safe_name(app.name, "app name")
            app_dir = splunkapps_path / app.name
            if not app_dir.is_dir():
                missing.append(app.name)

        if missing:
            raise ValueError(
                "App directories not found under SPLUNKAPPS_PATH: "
                + ", ".join(missing)
            )

    @staticmethod
    def _validate_no_overlap(apps: list[TargetApp], apps_to_remove: list[TargetApp]) -> None:
        deploy_names = {app.name for app in apps}
        remove_names = {app.name for app in apps_to_remove}
        conflicts = sorted(deploy_names & remove_names)
        if conflicts:
            raise ValueError(
                "These apps appear in both apps and splunk_apps_to_remove: "
                + ", ".join(conflicts)
            )

    def read_target_config(self, target_id: str) -> TargetConfig:
        group_vars_file, dest_key = self._target_spec(target_id)
        path = self.group_vars_dir / group_vars_file
        if not path.is_file():
            raise FileNotFoundError(f"group_vars file not found: {group_vars_file}")

        yaml = self._yaml_rt()
        with path.open(encoding="utf-8") as handle:
            data = yaml.load(handle)

        if not isinstance(data, dict):
            raise ValueError(f"Invalid group_vars file: {group_vars_file}")

        destination = data.get(dest_key)
        if destination is None:
            raise ValueError(f"Destination key not found in {group_vars_file}: {dest_key}")

        raw_apps = data.get("apps", [])
        if not isinstance(raw_apps, list):
            raise ValueError(f"Invalid apps list in {group_vars_file}")

        raw_removals = data.get("splunk_apps_to_remove", [])
        if not isinstance(raw_removals, list):
            raise ValueError(f"Invalid splunk_apps_to_remove list in {group_vars_file}")

        return TargetConfig(
            target_id=target_id,
            group=target_id,
            destination=str(destination),
            apps=self._parse_apps(raw_apps),
            apps_to_remove=self._parse_apps(raw_removals),
        )

    def write_target_apps(self, target_id: str, apps: list[TargetApp]) -> None:
        self.validate_apps_exist(apps)

        path, data, yaml = self._load_group_vars(target_id)
        raw_removals = data.get("splunk_apps_to_remove", [])
        if not isinstance(raw_removals, list):
            group_vars_file, _ = self._target_spec(target_id)
            raise ValueError(f"Invalid splunk_apps_to_remove list in {group_vars_file}")

        removals = self._parse_apps(raw_removals)
        self._validate_no_overlap(apps, removals)

        data["apps"] = self._apps_to_yaml(apps)
        self._save_group_vars(path, data, yaml)

    def write_target_removals(self, target_id: str, apps_to_remove: list[TargetApp]) -> None:
        for app in apps_to_remove:
            validate_safe_name(app.name, "app name")

        path, data, yaml = self._load_group_vars(target_id)
        raw_apps = data.get("apps", [])
        if not isinstance(raw_apps, list):
            group_vars_file, _ = self._target_spec(target_id)
            raise ValueError(f"Invalid apps list in {group_vars_file}")

        apps = self._parse_apps(raw_apps)
        self._validate_no_overlap(apps, apps_to_remove)

        data["splunk_apps_to_remove"] = self._apps_to_yaml(apps_to_remove)
        self._save_group_vars(path, data, yaml)

    def clear_target_removals(self, target_id: str) -> None:
        path, data, yaml = self._load_group_vars(target_id)
        raw_removals = data.get("splunk_apps_to_remove", [])
        if isinstance(raw_removals, list) and len(raw_removals) == 0:
            return

        data["splunk_apps_to_remove"] = []
        self._save_group_vars(path, data, yaml)
        self._commit_and_push(
            target_id,
            f"UI: cleared {target_id} app removals after deploy",
        )
