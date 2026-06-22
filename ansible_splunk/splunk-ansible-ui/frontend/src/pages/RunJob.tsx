import { useEffect, useState } from "react";

import {
  createJob,
  fetchEnvironments,
  fetchTargets,
} from "../api/client";
import type { Environment, Target } from "../api/types";
import JobLog from "../components/JobLog";
import { useJobStream } from "../hooks/useJobStream";

export default function RunJob() {
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [runnableTargets, setRunnableTargets] = useState<Target[]>([]);
  const [selectedEnvironment, setSelectedEnvironment] = useState("");
  const [selectedPlaybook, setSelectedPlaybook] = useState("");
  const [gitPullFirst, setGitPullFirst] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { lines, status, exitCode, isStreaming } = useJobStream(jobId);

  useEffect(() => {
    let cancelled = false;

    async function loadEnvironments() {
      setLoading(true);
      setError(null);

      try {
        const envs = await fetchEnvironments();
        if (cancelled) {
          return;
        }

        setEnvironments(envs);
        const defaultEnv =
          envs.find((env) => env.runnable)?.name ?? envs[0]?.name ?? "";
        setSelectedEnvironment((current) => current || defaultEnv);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load environments");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadEnvironments();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedEnvironment) {
      return;
    }

    let cancelled = false;

    async function loadTargets() {
      setError(null);

      try {
        const response = await fetchTargets(selectedEnvironment);
        const runnable = response.targets.filter((target) => target.runnable);

        if (cancelled) {
          return;
        }

        setRunnableTargets(runnable);
        setSelectedPlaybook((current) => {
          if (current && runnable.some((target) => target.id === current)) {
            return current;
          }
          return runnable[0]?.id ?? "";
        });
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load targets");
        }
      }
    }

    loadTargets();

    return () => {
      cancelled = true;
    };
  }, [selectedEnvironment]);

  async function handleRun() {
    if (!selectedPlaybook || !selectedEnvironment) {
      return;
    }

    const env = environments.find((item) => item.name === selectedEnvironment);
    if (!env?.runnable) {
      return;
    }

    setSubmitting(true);
    setError(null);
    setJobId(null);

    try {
      const job = await createJob({
        playbook: selectedPlaybook,
        environment: selectedEnvironment,
        git_pull_first: gitPullFirst,
      });
      setJobId(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start job");
    } finally {
      setSubmitting(false);
    }
  }

  const runnableEnvironments = environments.filter((env) => env.runnable);
  const selectedEnv = environments.find((env) => env.name === selectedEnvironment);
  const runDisabled =
    loading ||
    submitting ||
    isStreaming ||
    !selectedPlaybook ||
    !selectedEnv?.runnable;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <span className="mr-3 inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Loading run options…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">Run Job</h2>
        <p className="mt-2 text-sm text-slate-600">
          Run allowed playbooks against configured environments.
        </p>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          <p className="text-sm">{error}</p>
        </div>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Environment</span>
            <select
              value={selectedEnvironment}
              onChange={(event) => setSelectedEnvironment(event.target.value)}
              disabled={isStreaming || submitting}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 disabled:bg-slate-50"
            >
              {runnableEnvironments.map((env) => (
                <option key={env.name} value={env.name}>
                  {env.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Playbook</span>
            <select
              value={selectedPlaybook}
              onChange={(event) => setSelectedPlaybook(event.target.value)}
              disabled={isStreaming || submitting || runnableTargets.length === 0}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-slate-900 disabled:bg-slate-50"
            >
              {runnableTargets.length === 0 ? (
                <option value="">No runnable playbooks</option>
              ) : (
                runnableTargets.map((target) => (
                  <option key={target.id} value={target.id}>
                    {target.display_name ?? target.id}
                  </option>
                ))
              )}
            </select>
          </label>
        </div>

        <label className="mt-4 flex items-center gap-2">
          <input
            type="checkbox"
            checked={gitPullFirst}
            onChange={(event) => setGitPullFirst(event.target.checked)}
            disabled={isStreaming || submitting}
            className="h-4 w-4 rounded border-slate-300"
          />
          <span className="text-sm text-slate-700">Git pull first (run git_client before selected playbook)</span>
        </label>

        <button
          type="button"
          onClick={handleRun}
          disabled={runDisabled}
          className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {submitting || isStreaming ? "Running…" : "Run"}
        </button>
      </section>

      {jobId && (
        <section>
          <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
            Job Output
          </h3>
          <JobLog
            lines={lines}
            status={status}
            exitCode={exitCode}
            isStreaming={isStreaming}
          />
        </section>
      )}
    </div>
  );
}
