# splunk-deployment-config

Ansible automation for distributing Splunk apps to Deployment Server, Cluster Manager, Search Head Cluster Deployer, standalone Search Heads, and SC4S forwarders.

This repository is **configuration and playbooks only**. Pair it with **splunk-ansible-ui** for a browser-based operator experience.

---

## Contents

```
.
├── ansible.cfg
├── apps/                    # Splunk app directories (one folder per app)
├── playbooks/
│   ├── git_client.yml
│   ├── deploymentserver.yml
│   ├── clustermanager.yml
│   ├── shdeployer.yml
│   ├── standalone.yml
│   ├── sc4s_forwarder.yml
│   └── tasks/deploy_apps.yml
└── inventory/
    ├── test
    ├── production
    └── group_vars/
```

---

## Prerequisites

1. **Splunk apps** — one subdirectory per app under `apps/`
2. **Ansible** 2.14+ (or use splunk-ansible-ui Docker stack)
3. **Collections**:

   ```bash
   ansible-galaxy collection install ansible.posix community.docker
   ```

4. **SSH access** — playbooks run as the `splunk` user on target hosts (SC4S uses `root` for paths under `/opt`)
5. **Git** — required when using splunk-ansible-ui **Apps** page (commit and push)

---

## Getting started

Download with [degit](https://github.com/Rich-Harris/degit) (recommended) or download ZIP from GitHub. These templates live in the [seynur-tools](https://github.com/seynur/seynur-tools) monorepo under `ansible_splunk/` (not a standalone template repository).

Requires Node.js. If unavailable, download ZIP from:
https://github.com/seynur/seynur-tools/archive/main.zip

GitHub extracts to `seynur-tools-main/` — `cd seynur-tools-main/ansible_splunk/splunk-deployment-config`

### 1. Download the template and point at your repository

```bash
npx degit seynur/seynur-tools/ansible_splunk/splunk-deployment-config splunk-deployment-config
cd splunk-deployment-config
git init
git remote add origin https://github.com/your-org/your-splunk-config.git
```

Alternative: download ZIP from GitHub and extract:

```bash
curl -LO https://github.com/seynur/seynur-tools/archive/main.zip
unzip main.zip
cd seynur-tools-main/ansible_splunk/splunk-deployment-config
git init
git remote add origin https://github.com/your-org/your-splunk-config.git
```

### 2. Add Splunk apps

Place app directories under `apps/`:

```
apps/your_app_name/
```

See `apps/README.md` for layout guidance.

### 3. Configure inventory

Edit `inventory/test` and `inventory/production` with your hostnames or IP addresses.

**Example** (`inventory/test`):

```ini
[deploymentserver]
ds01.example.com ansible_user=splunk

[clustermanager]
cm01.example.com ansible_user=splunk

[shdeployer]
shdeployer01.example.com ansible_user=splunk

[standalone]
sh01.example.com ansible_user=splunk

[sc4s_forwarder]
sc4s01.example.com ansible_user=root

[git_client]
localhost ansible_connection=local
```

Use the same group names in `inventory/production` with your production hostnames.

### 4. Test vs production

| Inventory | Purpose |
|-----------|---------|
| `inventory/test` | Non-production Splunk hosts. Use for validation before promoting changes. |
| `inventory/production` | Production Splunk hosts. Restrict **Run Job** access in splunk-ansible-ui via `ALLOWED_ENVIRONMENTS`. |

Both inventories share the same `group_vars/` — app lists and destinations apply to whichever inventory you run against. Hostnames differ per file.

In splunk-ansible-ui, only environments listed in `ALLOWED_ENVIRONMENTS` appear in **Run Job**. The **Dashboard** shows targets from the `test` inventory by default.

### 5. Configure targets (`group_vars`)

Each deploy target has a file under `inventory/group_vars/`:

```yaml
splunk_dest: /opt/splunk/etc/deployment-apps/
apps:
  - name: your_app_name
splunk_apps_to_remove:
  - name: deprecated_app_name
```

| Target file | Destination variable | Default path |
|-------------|---------------------|--------------|
| `deploymentserver.yml` | `splunk_dest` | `/opt/splunk/etc/deployment-apps/` |
| `clustermanager.yml` | `splunk_dest` | `/opt/splunk/etc/manager-apps/` |
| `shdeployer.yml` | `splunk_dest` | `/opt/splunk/etc/shcluster/apps/` |
| `standalone.yml` | `splunk_dest` | `/opt/splunk/etc/apps/` |
| `sc4s_forwarder.yml` | `sc4s_splunk_dest` | `/opt` |

`inventory/group_vars/all.yml` sets the apps source path:

```yaml
git_splunkapps_path: "{{ lookup('env', 'SPLUNKAPPS_PATH') | default(playbook_dir + '/../apps', true) }}"
```

### 6. Push your configuration

After adding apps and editing inventory and `group_vars`:

```bash
git add .
git commit -m "Initial customer configuration"
git push -u origin main
```

Configure Git user identity on the UI host (or inside the backend container) before using **Apps**:

```bash
git config user.email "ops@example.com"
git config user.name "Splunk Ops"
```

splunk-ansible-ui **Apps** commits and pushes to this repository. Your remote must be set (see step 1) with push access.

---

## splunk-ansible-ui integration

1. Download the template with degit, set your Git remote, and complete inventory, `group_vars`, and `apps/` setup in this repo.
2. Push your initial configuration to your remote (see above).
3. On the UI host, set `DEPLOYMENT_ROOT` in splunk-ansible-ui `.env` to the **host path** of this checkout.
4. Start splunk-ansible-ui with Docker Compose (`docker compose up --build`).
5. Open http://localhost:
   - **Dashboard** — verify targets and hosts
   - **Apps** — manage deploy/removal lists (auto commit + push)
   - **Run Job** — run playbooks; enable **Git pull first** to sync from remote before deploy

The UI mounts this repo at `/deployment` inside the backend container. `SPLUNKAPPS_PATH` is `/deployment/apps` automatically.

---

## Running playbooks (CLI)

From this repository root:

```bash
export SPLUNKAPPS_PATH=/path/to/splunk-deployment-config/apps

# Optional: refresh repo (apps + inventory + group_vars)
ansible-playbook -i inventory/test playbooks/git_client.yml

# Deploy to deployment server
ansible-playbook -i inventory/test playbooks/deploymentserver.yml
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `SPLUNKAPPS_PATH` | Path to `apps/` on the Ansible controller. Defaults to `apps/` under this repo. |

When used with **splunk-ansible-ui**, set `DEPLOYMENT_ROOT` on the UI host to this repository's path (see splunk-ansible-ui README).

---

## Inventory groups

| Group | Playbook |
|-------|----------|
| `deploymentserver` | `deploymentserver.yml` |
| `clustermanager` | `clustermanager.yml` |
| `shdeployer` | `shdeployer.yml` |
| `standalone` | `standalone.yml` |
| `sc4s_forwarder` | `sc4s_forwarder.yml` |
| `git_client` | `git_client.yml` |

---

## Deploy pattern

1. **Remove** apps listed in `splunk_apps_to_remove` from the target destination
2. **Stage** apps from `apps/<name>/` on the controller
3. **Sync** to `splunk_dest` on each target host

Post-deploy Splunk reloads (deployment server reload, cluster bundle push, etc.) are not automated in this template.
