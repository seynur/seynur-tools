from fastapi import APIRouter, HTTPException, Query

from app.models.target import TargetsResponse
from app.services.config_reader import ConfigReader

router = APIRouter()
_reader = ConfigReader()


@router.get("/targets", response_model=TargetsResponse)
def get_targets(
    environment: str = Query(default="test"),
) -> TargetsResponse:
    try:
        return _reader.read_targets(environment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Environment not found") from exc
