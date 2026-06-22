from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import DEPLOYMENT_ROOT
from app.services.config_reader import validate_safe_name

router = APIRouter()


class InventoryGroupHosts(BaseModel):
    group: str
    hosts: list[str]


class InventoryResponse(BaseModel):
    environment: str
    groups: list[InventoryGroupHosts]


def _resolve_inventory_path(environment: str) -> Path:
    validate_safe_name(environment, "environment")
    inventory_dir = DEPLOYMENT_ROOT / "inventory"
    inventory_path = (inventory_dir / environment).resolve()
    inventory_root = inventory_dir.resolve()
    if not inventory_path.is_relative_to(inventory_root):
        raise ValueError(f"Invalid environment: {environment!r}")
    if not inventory_path.is_file():
        raise FileNotFoundError(f"Inventory not found: inventory/{environment}")
    return inventory_path


def _list_inventory_groups(inventory_path: Path) -> list[str]:
    groups: list[str] = []
    for raw_line in inventory_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("[") or not line.endswith("]"):
            continue
        section = line[1:-1]
        if section.endswith(":children") or section.endswith(":vars"):
            continue
        groups.append(section)
    return groups


def _is_section_header(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def _find_group_section(lines: list[str], group: str) -> tuple[int, int]:
    header = f"[{group}]"
    start: int | None = None

    for index, line in enumerate(lines):
        if line.strip() == header:
            start = index
            break

    if start is None:
        raise ValueError(f"Inventory group not found: {group}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _is_section_header(lines[index]):
            end = index
            break

    return start, end


def _read_group_host_lines(content: str, group: str) -> list[str]:
    lines = content.splitlines(keepends=True)
    start, end = _find_group_section(lines, group)
    hosts: list[str] = []

    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _is_section_header(line):
            break
        hosts.append(stripped)

    return hosts


def _read_inventory_hosts(environment: str, group: str) -> list[str]:
    validate_safe_name(group, "group")
    path = _resolve_inventory_path(environment)
    return _read_group_host_lines(path.read_text(encoding="utf-8"), group)


def _handle_inventory_errors(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
    raise exc


@router.get("/inventory/{environment}", response_model=InventoryResponse)
def get_inventory(environment: str) -> InventoryResponse:
    try:
        inventory_path = _resolve_inventory_path(environment)
        groups = [
            InventoryGroupHosts(
                group=group,
                hosts=_read_inventory_hosts(environment, group),
            )
            for group in _list_inventory_groups(inventory_path)
        ]
        return InventoryResponse(environment=environment, groups=groups)
    except (ValueError, FileNotFoundError) as exc:
        _handle_inventory_errors(exc)
        raise
