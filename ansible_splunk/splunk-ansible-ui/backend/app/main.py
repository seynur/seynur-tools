from fastapi import FastAPI

from app.api import config, environments, git, health, inventory, jobs, settings, targets

app = FastAPI(title="Splunk Ansible Web API")

app.include_router(health.router, prefix="/api")
app.include_router(environments.router, prefix="/api")
app.include_router(targets.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(git.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
