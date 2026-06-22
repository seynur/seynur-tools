export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface Environment {
  name: string;
  runnable: boolean;
}

export interface TargetApp {
  name: string;
}

export interface Target {
  id: string;
  playbook: string;
  group: string;
  hosts: string[];
  destination: string | null;
  apps: TargetApp[];
  apps_to_remove: TargetApp[];
  runnable: boolean;
  display_name?: string;
}

export interface TargetsResponse {
  environment: string;
  git_path: string;
  targets: Target[];
}

export interface Job {
  id: string;
  playbook: string;
  environment: string;
  git_pull_first?: boolean;
  status: JobStatus;
  exit_code: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobRequest {
  playbook: string;
  environment: string;
  git_pull_first?: boolean;
}

export interface JobOutput {
  job_id: string;
  lines: string[];
}

export interface LogLine {
  type: "log";
  line: string;
}

export interface JobComplete {
  status: JobStatus;
  exit_code: number | null;
}

export interface GitStatus {
  files: string[];
}

export interface TargetConfig {
  target_id: string;
  destination: string;
  apps: TargetApp[];
  apps_to_remove: TargetApp[];
}

export interface TargetConfigUpdate {
  apps: TargetApp[];
}

export interface TargetRemovalsUpdate {
  apps_to_remove: TargetApp[];
}

export interface Settings {
  splunkapps_path: string;
  allowed_environments: string;
  allowed_playbooks: string;
  remote_user: string;
}
