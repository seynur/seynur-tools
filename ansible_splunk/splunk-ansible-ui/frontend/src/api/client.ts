import type {
  Environment,
  GitStatus,
  Job,
  JobOutput,
  JobRequest,
  Settings,
  TargetApp,
  TargetConfig,
  TargetConfigUpdate,
  TargetRemovalsUpdate,
  TargetsResponse,
} from "./types";

const API_BASE = "/api";

interface EnvironmentsApiResponse {
  environments: Array<{
    name: string;
    inventory_file: string;
    runnable: boolean;
  }>;
}

interface JobCreatedApiResponse {
  id: string;
  status: Job["status"];
}

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : response.statusText;
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function fetchEnvironments(): Promise<Environment[]> {
  const data = await fetchJson<EnvironmentsApiResponse>(`${API_BASE}/environments`);
  return data.environments.map(({ name, runnable }) => ({ name, runnable }));
}

export async function fetchTargets(environment: string): Promise<TargetsResponse> {
  const params = new URLSearchParams({ environment });
  return fetchJson<TargetsResponse>(`${API_BASE}/targets?${params}`);
}

export async function createJob(request: JobRequest): Promise<Job> {
  const created = await fetchJson<JobCreatedApiResponse>(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  return fetchJson<Job>(`${API_BASE}/jobs/${created.id}`);
}

export async function fetchJobs(): Promise<Job[]> {
  return fetchJson<Job[]>(`${API_BASE}/jobs`);
}

export async function fetchJob(jobId: string): Promise<Job> {
  return fetchJson<Job>(`${API_BASE}/jobs/${jobId}`);
}

export async function fetchJobOutput(jobId: string): Promise<JobOutput> {
  return fetchJson<JobOutput>(`${API_BASE}/jobs/${jobId}/output`);
}

interface AvailableAppsResponse {
  apps: string[];
}

export async function fetchAvailableApps(): Promise<AvailableAppsResponse> {
  return fetchJson<AvailableAppsResponse>(`${API_BASE}/config/apps`);
}

export async function fetchTargetConfig(targetId: string): Promise<TargetConfig> {
  return fetchJson<TargetConfig>(`${API_BASE}/config/${targetId}`);
}

export async function updateTargetApps(
  targetId: string,
  apps: TargetApp[],
): Promise<TargetConfig> {
  const body: TargetConfigUpdate = { apps };
  return fetchJson<TargetConfig>(`${API_BASE}/config/${targetId}/apps`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateTargetRemovals(
  targetId: string,
  appsToRemove: TargetApp[],
): Promise<TargetConfig> {
  const body: TargetRemovalsUpdate = { apps_to_remove: appsToRemove };
  return fetchJson<TargetConfig>(`${API_BASE}/config/${targetId}/removals`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function fetchGitStatus(): Promise<GitStatus> {
  return fetchJson<GitStatus>(`${API_BASE}/git/status`);
}

interface SettingsApiResponse {
  SPLUNKAPPS_PATH: string;
  ALLOWED_ENVIRONMENTS: string;
  ALLOWED_PLAYBOOKS: string;
  remote_user: string;
}

function settingsFromApi(data: SettingsApiResponse): Settings {
  return {
    splunkapps_path: data.SPLUNKAPPS_PATH,
    allowed_environments: data.ALLOWED_ENVIRONMENTS,
    allowed_playbooks: data.ALLOWED_PLAYBOOKS,
    remote_user: data.remote_user,
  };
}

function settingsToApi(settings: Partial<Settings>): Partial<SettingsApiResponse> {
  const body: Partial<SettingsApiResponse> = {};

  if (settings.splunkapps_path !== undefined) {
    body.SPLUNKAPPS_PATH = settings.splunkapps_path;
  }
  if (settings.allowed_environments !== undefined) {
    body.ALLOWED_ENVIRONMENTS = settings.allowed_environments;
  }
  if (settings.allowed_playbooks !== undefined) {
    body.ALLOWED_PLAYBOOKS = settings.allowed_playbooks;
  }
  if (settings.remote_user !== undefined) {
    body.remote_user = settings.remote_user;
  }

  return body;
}

export async function fetchSettings(): Promise<Settings> {
  const data = await fetchJson<SettingsApiResponse>(`${API_BASE}/settings`);
  return settingsFromApi(data);
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  const data = await fetchJson<SettingsApiResponse>(`${API_BASE}/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settingsToApi(settings)),
  });
  return settingsFromApi(data);
}
