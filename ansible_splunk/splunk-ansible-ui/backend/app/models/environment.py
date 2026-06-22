from pydantic import BaseModel


class Environment(BaseModel):
    name: str
    inventory_file: str
    runnable: bool


class EnvironmentsResponse(BaseModel):
    environments: list[Environment]
