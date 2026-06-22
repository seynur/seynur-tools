# Splunk Ansible UI

Web application for managing Splunk Ansible deployments: run playbooks, manage apps per target, and view job history.

This repository contains:

- `backend/` — FastAPI API (job runner, apps manager, Git integration)
- `frontend/` — React + TypeScript UI served by nginx in production
- `docker-compose.yml` — production deployment stack (UI + API)

Ansible playbooks and inventory live in a separate **splunk-deployment-config** repository. The UI reads and updates that repo at runtime via `DEPLOYMENT_ROOT`.

---

## Prerequisites

- Docker and Docker Compose
- A configured **splunk-deployment-config** checkout (inventory, `group_vars`, `apps/`, Git remote)
- Network access from the backend container to your Splunk hosts over SSH
- Ansible collections (`ansible.posix`, `community.docker`) — installed in the backend image

Complete **splunk-deployment-config** setup (including Git remote) before starting the UI. See the combined guide in the parent `release/README.md` if you use the release bundle.

---

## Quick start (Docker Compose)

### 1. Clone both repositories

```bash
git clone <splunk-ansible-ui-url> splunk-ansible-ui
git clone <splunk-deployment-config-url> splunk-deployment-config
```

Example layout:

```
/opt/splunk/
  splunk-ansible-ui/
  splunk-deployment-config/
```

### 2. Configure environment

Copy the example file and edit paths:

```bash
cd splunk-ansible-ui
cp .env.example .env
```

`.env` (repo root, next to `docker-compose.yml`):

```env
DEPLOYMENT_ROOT=/absolute/path/to/splunk-deployment-config
ALLOWED_ENVIRONMENTS=test,production
ALLOWED_PLAYBOOKS=git_client,deploymentserver,clustermanager,shdeployer,standalone,sc4s_forwarder
DATABASE_PATH=/app/data/jobs.db
```

| Variable | Purpose |
|----------|---------|
| `DEPLOYMENT_ROOT` | **Host path** to `splunk-deployment-config`. Mounted read-only at `/deployment` in the backend container. |
| `ALLOWED_ENVIRONMENTS` | Inventories shown in **Run Job** (comma-separated). |
| `ALLOWED_PLAYBOOKS` | Playbooks permitted for job execution. |
| `DATABASE_PATH` | SQLite path inside the container (`/app/data/jobs.db` with the default volume). |

Inside the container, `SPLUNKAPPS_PATH` is set automatically to `/deployment/apps`. You do not need to set it in `.env`.

Settings can also be changed later in the UI under **Settings** (stored in SQLite and override `.env` defaults).

For running the backend outside Docker, copy `backend/.env.example` to `backend/.env` and use host paths.

### 3. Configure SSH for Ansible (required for Run Job)

Playbooks run inside the backend container. Mount your SSH private key and `known_hosts` so Ansible can reach Splunk hosts.

Add volumes under the `backend` service in `docker-compose.yml` (example):

```yaml
volumes:
  - ~/.ssh:/root/.ssh:ro
```

Ensure the key is authorized on target hosts for the `splunk` user (or the user defined in your inventory). Test from the container:

```bash
docker compose exec backend ssh splunk@your-splunk-host
```

### 4. Git requirements (required for Apps Manager)

The **Apps** page commits and pushes changes to `splunk-deployment-config`. The mounted deployment repo must:

1. Be a Git repository (`git init` or cloned from your remote)
2. Have `user.name` and `user.email` configured for commits
3. Have a **remote** configured (`git remote add origin <url>`) with push access

If Git is not initialized or push fails, app changes are written locally but not published to your remote.

### 5. Start the stack

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| UI | http://localhost |
| API | http://localhost/api |

The backend is not exposed on the host. Nginx in the frontend container proxies `/api` (and WebSockets) to the backend service.

Ensure port **80** is free on the host, or change the frontend port mapping in `docker-compose.yml`.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEPLOYMENT_ROOT` | Yes (Compose) | — | **Host path** to `splunk-deployment-config`. Mounted at `/deployment` in the backend container. |
| `ALLOWED_ENVIRONMENTS` | No | `test,production` | Inventories permitted for **Run Job** |
| `ALLOWED_PLAYBOOKS` | No | All deploy playbooks | Playbooks permitted for job execution |
| `DATABASE_PATH` | No | `/app/data/jobs.db` (Compose) | SQLite database for job history |
| `SPLUNKAPPS_PATH` | No | `/deployment/apps` (Compose) | Path to Splunk app directories inside the container |

---

## UI features

- **Dashboard** — read-only view of targets, hosts, apps, and pending removals
- **Apps** — manage `apps[]` and removal lists per target; changes commit and push to Git
- **Run Job** — execute playbooks with optional git pull first
- **History** — job list and log output
- **Settings** — paths, allowed environments, and allowed playbooks

---

## Workflow

1. Add Splunk app directories under `splunk-deployment-config/apps/`.
2. Use **Apps** to select which apps deploy to each target (commits and pushes to Git).
3. On **Run Job**, enable **Git pull first** if the controller should sync from remote before running.
4. Run the target playbook against `test` or `production`.
5. Pending removals are cleared from `group_vars` automatically after a successful deploy.

---

## Security

Authentication is not included in this release. Do not expose the UI to untrusted networks without a reverse proxy, TLS, and access controls.

---

## Optional: local development without Docker

For frontend or backend development only:

```bash
# Backend
cd backend && cp .env.example .env && pip install -e .
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 (Vite dev server proxies `/api` to http://localhost:8000). This path is for development, not production deployment.
