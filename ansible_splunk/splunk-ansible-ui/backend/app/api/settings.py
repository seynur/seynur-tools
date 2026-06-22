from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.config import SETTING_KEYS, get_all_settings
from app.services.settings_store import SettingsStore

router = APIRouter()
_store = SettingsStore()


class SettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    SPLUNKAPPS_PATH: str
    ALLOWED_ENVIRONMENTS: str
    ALLOWED_PLAYBOOKS: str
    remote_user: str


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    SPLUNKAPPS_PATH: str | None = None
    ALLOWED_ENVIRONMENTS: str | None = None
    ALLOWED_PLAYBOOKS: str | None = None
    remote_user: str | None = None


def _to_response() -> SettingsResponse:
    values = get_all_settings()
    return SettingsResponse(**values)


@router.get("/settings", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    return _to_response()


@router.put("/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate) -> SettingsResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    for key, value in updates.items():
        if key not in SETTING_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")
        if not value.strip():
            raise HTTPException(status_code=400, detail=f"Setting cannot be empty: {key}")
        _store.set(key, value.strip())

    return _to_response()
