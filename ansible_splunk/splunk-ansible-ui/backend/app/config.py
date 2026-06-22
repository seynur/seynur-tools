import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

_DEFAULT_DEPLOYMENT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "deployment"
_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"
_DEFAULT_REMOTE_USER = "splunk"
_DEFAULT_ALLOWED_ENVIRONMENTS = ["test", "docker-test"]
_DEFAULT_ALLOWED_PLAYBOOKS = [
    "git_client",
    "deploymentserver",
    "clustermanager",
    "shdeployer",
    "standalone",
    "sc4s_forwarder",
]

SETTING_KEYS = (
    "SPLUNKAPPS_PATH",
    "ALLOWED_ENVIRONMENTS",
    "ALLOWED_PLAYBOOKS",
    "remote_user",
)

_settings_store = None


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value:
        return Path(value).expanduser().resolve()
    return default.resolve()


def _list_from_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_settings_store():
    global _settings_store
    if _settings_store is None:
        from app.services.settings_store import SettingsStore

        _settings_store = SettingsStore()
    return _settings_store


def _default_splunkapps_path() -> str:
    env_value = os.environ.get("SPLUNKAPPS_PATH")
    if env_value:
        return env_value
    deployment_root = _path_from_env("DEPLOYMENT_ROOT", _DEFAULT_DEPLOYMENT_ROOT)
    return str((deployment_root / "apps").resolve())


def _default_setting_value(key: str) -> str:
    if key == "SPLUNKAPPS_PATH":
        return _default_splunkapps_path()
    if key == "ALLOWED_ENVIRONMENTS":
        return os.environ.get(
            "ALLOWED_ENVIRONMENTS",
            ",".join(_DEFAULT_ALLOWED_ENVIRONMENTS),
        )
    if key == "ALLOWED_PLAYBOOKS":
        return os.environ.get(
            "ALLOWED_PLAYBOOKS",
            ",".join(_DEFAULT_ALLOWED_PLAYBOOKS),
        )
    if key == "remote_user":
        return _DEFAULT_REMOTE_USER
    raise KeyError(f"Unknown setting: {key}")


def get_setting(key: str, env_fallback: str | None = None) -> str | None:
    value = _get_settings_store().get(key)
    if value is not None:
        return value
    if env_fallback is not None:
        return env_fallback
    return _default_setting_value(key)


def get_all_settings() -> dict[str, str]:
    return {
        key: get_setting(key, _default_setting_value(key)) or ""
        for key in SETTING_KEYS
    }


class _SettingList:
    def __init__(self, key: str, default: list[str]) -> None:
        self._key = key
        self._default = default

    def _values(self) -> list[str]:
        raw = get_setting(self._key, ",".join(self._default))
        if not raw:
            return list(self._default)
        return [item.strip() for item in raw.split(",") if item.strip()]

    def __contains__(self, item: object) -> bool:
        return item in self._values()

    def __iter__(self) -> Iterator[str]:
        return iter(self._values())

    def __repr__(self) -> str:
        return repr(self._values())


DEPLOYMENT_ROOT = _path_from_env("DEPLOYMENT_ROOT", _DEFAULT_DEPLOYMENT_ROOT)
DATABASE_PATH = _path_from_env("DATABASE_PATH", _DEFAULT_DATABASE_PATH)
ALLOWED_ENVIRONMENTS = _SettingList("ALLOWED_ENVIRONMENTS", _DEFAULT_ALLOWED_ENVIRONMENTS)
ALLOWED_PLAYBOOKS = _SettingList("ALLOWED_PLAYBOOKS", _DEFAULT_ALLOWED_PLAYBOOKS)


def get_splunkapps_path() -> str:
    return get_setting("SPLUNKAPPS_PATH", _default_setting_value("SPLUNKAPPS_PATH")) or _default_splunkapps_path()
