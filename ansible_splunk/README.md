# Release Package

This folder contains two repositories intended to be published separately:

| Directory | Purpose |
|-----------|---------|
| **splunk-ansible-ui** | Web UI product — run Ansible playbooks, manage apps, view job history |
| **splunk-deployment-config** | Customer configuration template — playbooks, inventory, and `group_vars` |

---

## End-to-end getting started

### Step 1: Download and configure splunk-deployment-config

These templates live in the [seynur-tools](https://github.com/seynur/seynur-tools) monorepo under `ansible_splunk/`. Use [degit](https://github.com/Rich-Harris/degit) to fetch a subfolder (requires Node.js):

```bash
npx degit seynur/seynur-tools/ansible_splunk/splunk-deployment-config splunk-deployment-config
cd splunk-deployment-config
git init
git remote add origin https://github.com/your-org/your-splunk-config.git
```

1. Add Splunk app directories under `apps/` (one folder per app).
2. Edit `inventory/test` and `inventory/production` with your Splunk hostnames.
3. Edit `inventory/group_vars/*.yml` — set `apps[]` and `splunk_dest` per target.

See **splunk-deployment-config/README.md** for inventory examples and target paths.

### Step 2: Push to your repository

```bash
git add .
git commit -m "Initial customer configuration"
git push -u origin main
```

Required for splunk-ansible-ui **Apps** page (auto commit and push). Configure `user.name` and `user.email` on the machine that runs the UI.

### Step 3: Start splunk-ansible-ui

```bash
npx degit seynur/seynur-tools/ansible_splunk/splunk-ansible-ui splunk-ansible-ui
cd splunk-ansible-ui
cp .env.example .env
# Edit DEPLOYMENT_ROOT to the host path of your splunk-deployment-config checkout
docker compose up --build
```

### Step 4: Verify Dashboard

Open http://localhost and confirm:

- **Environments** shows allowed inventories (e.g. `test`, `production`)
- **Targets** cards list hosts, apps, and destinations from your inventory

### Step 5: Deploy apps

1. **Apps** — add apps to targets (commits and pushes to Git).
2. **Run Job** — select environment and playbook; enable **Git pull first** if the controller should sync from remote.
3. Run the job and review output in **History**.

---

## SSH keys for Ansible

Playbooks run inside the splunk-ansible-ui backend container. Mount SSH credentials so Ansible can reach Splunk hosts.

Example addition to `splunk-ansible-ui/docker-compose.yml` under `backend.volumes`:

```yaml
- ~/.ssh:/root/.ssh:ro
```

Ensure:

- Your private key is authorized on Splunk hosts for `ansible_user` (usually `splunk`)
- Host keys are in `~/.ssh/known_hosts` (or accept on first connect)
- The UI host can reach Splunk management ports over the network

Test from the running container:

```bash
docker compose exec backend ssh splunk@your-splunk-host
```

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| **Apps** page shows "No apps found" | Empty `apps/` directory | Add Splunk app folders under `splunk-deployment-config/apps/` |
| Git push fails after saving in **Apps** | No remote or no credentials | `git remote -v` in deployment-config; configure SSH or HTTPS credentials in the container |
| **Run Job** fails with SSH errors | Keys not mounted or wrong user | Mount `~/.ssh`; verify `ansible_user` in inventory |
| Environment missing in **Run Job** | Not in `ALLOWED_ENVIRONMENTS` | Set `ALLOWED_ENVIRONMENTS=test,production` in `.env` or **Settings** |
| Dashboard shows no hosts | Inventory not edited | Add hostnames under the correct `[group]` sections |
| `docker compose` fails on volume mount | `DEPLOYMENT_ROOT` unset or wrong path | Set absolute host path in `.env` |
| Port 80 already in use | Another web server on host | Change frontend ports in `docker-compose.yml` (e.g. `8080:80`) |
| Changes not on Splunk hosts | Only updated Git, did not run playbook | Use **Run Job** after **Apps** changes; enable **Git pull first** on the controller |

---

## Per-repository documentation

- **splunk-ansible-ui/README.md** — Docker deployment, environment variables, Git and SSH setup
- **splunk-deployment-config/README.md** — inventory, group_vars, CLI playbooks, UI integration

Download each template with degit (see steps above) and point `splunk-deployment-config` at your own Git remote before customizing.
