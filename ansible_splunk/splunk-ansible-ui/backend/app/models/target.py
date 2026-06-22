from pydantic import BaseModel


class TargetApp(BaseModel):
    name: str


class Target(BaseModel):
    id: str
    playbook: str
    group: str
    hosts: list[str]
    destination: str | None
    apps: list[TargetApp]
    apps_to_remove: list[TargetApp] = []
    runnable: bool
    display_name: str


class TargetsResponse(BaseModel):
    environment: str
    git_path: str
    targets: list[Target]
