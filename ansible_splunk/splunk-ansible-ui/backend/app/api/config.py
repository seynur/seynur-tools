from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_splunkapps_path
from app.models.target import TargetApp
from app.services.config_writer import ConfigWriter, TargetConfig
from app.services.git_service import GitService

router = APIRouter()
_writer = ConfigWriter()
_git = GitService()


class AvailableAppsResponse(BaseModel):
    apps: list[str]


class TargetConfigResponse(BaseModel):
    target_id: str
    group: str
    destination: str
    apps: list[TargetApp]
    apps_to_remove: list[TargetApp]


class TargetAppsUpdate(BaseModel):
    apps: list[TargetApp]


class TargetRemovalsUpdate(BaseModel):
    apps_to_remove: list[TargetApp]


class ClearRemovalsResponse(BaseModel):
    success: bool


def _to_response(config: TargetConfig) -> TargetConfigResponse:
    return TargetConfigResponse(
        target_id=config.target_id,
        group=config.group,
        destination=config.destination,
        apps=config.apps,
        apps_to_remove=config.apps_to_remove,
    )


def _handle_config_errors(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        message = str(exc)
        if "no editable configuration" in message or "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    raise exc


def _commit_and_push(target_id: str) -> None:
    relative_path = _writer.group_vars_relative_path(target_id)
    commit_result = _git.commit_changes(f"UI: updated {target_id} apps", [relative_path])
    if not commit_result.success:
        raise ValueError("Nothing to commit")

    push_result = _git.push_changes()
    if not push_result.success:
        raise ValueError(push_result.message)


@router.get("/config/apps", response_model=AvailableAppsResponse)
def list_available_apps() -> AvailableAppsResponse:
    splunkapps_path = get_splunkapps_path()
    if not splunkapps_path.strip():
        raise HTTPException(status_code=400, detail="SPLUNKAPPS_PATH is not set")

    path = Path(splunkapps_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"SPLUNKAPPS_PATH is not a directory: {path}",
        )

    apps = sorted(
        item.name
        for item in path.iterdir()
        if item.is_dir() and not item.name.startswith(".")
    )
    return AvailableAppsResponse(apps=apps)


@router.put("/config/{target_id}/apps", response_model=TargetConfigResponse)
def update_target_apps(target_id: str, body: TargetAppsUpdate) -> TargetConfigResponse:
    try:
        _writer.write_target_apps(target_id, body.apps)
        _commit_and_push(target_id)
        return _to_response(_writer.read_target_config(target_id))
    except (ValueError, FileNotFoundError) as exc:
        _handle_config_errors(exc)
        raise


@router.put("/config/{target_id}/removals", response_model=TargetConfigResponse)
def update_target_removals(
    target_id: str,
    body: TargetRemovalsUpdate,
) -> TargetConfigResponse:
    try:
        _writer.write_target_removals(target_id, body.apps_to_remove)
        _commit_and_push(target_id)
        return _to_response(_writer.read_target_config(target_id))
    except (ValueError, FileNotFoundError) as exc:
        _handle_config_errors(exc)
        raise


@router.post("/config/{target_id}/clear-removals", response_model=ClearRemovalsResponse)
def clear_target_removals(target_id: str) -> ClearRemovalsResponse:
    try:
        _writer.clear_target_removals(target_id)
        return ClearRemovalsResponse(success=True)
    except (ValueError, FileNotFoundError) as exc:
        _handle_config_errors(exc)
        raise


@router.get("/config/{target_id}", response_model=TargetConfigResponse)
def get_target_config(target_id: str) -> TargetConfigResponse:
    try:
        return _to_response(_writer.read_target_config(target_id))
    except (ValueError, FileNotFoundError) as exc:
        _handle_config_errors(exc)
        raise
