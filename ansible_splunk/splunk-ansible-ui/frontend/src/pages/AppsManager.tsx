import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchAvailableApps,
  fetchEnvironments,
  fetchTargetConfig,
  fetchTargets,
  updateTargetApps,
  updateTargetRemovals,
} from "../api/client";
import type { Target, TargetApp, TargetConfig } from "../api/types";

interface WritableTarget {
  id: string;
  display_name: string;
}

interface GitPullResult {
  success: boolean;
  message: string;
}

async function fetchGitPull(): Promise<GitPullResult> {
  const response = await fetch("/api/git/pull");
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : response.statusText;
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return body as GitPullResult;
}

const WRITABLE_TARGET_IDS = new Set([
  "deploymentserver",
  "clustermanager",
  "shdeployer",
  "standalone",
  "sc4s_forwarder",
]);

function isWritableTarget(target: Target): target is Target & { id: string } {
  return WRITABLE_TARGET_IDS.has(target.id);
}

export default function AppsManager() {
  const [availableApps, setAvailableApps] = useState<string[]>([]);
  const [writableTargets, setWritableTargets] = useState<WritableTarget[]>([]);
  const [environment, setEnvironment] = useState("test");
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [config, setConfig] = useState<TargetConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showApplyBanner, setShowApplyBanner] = useState(false);
  const [gitPullMessage, setGitPullMessage] = useState<string | null>(null);

  const loadTargetConfig = useCallback(async (targetId: string) => {
    const targetConfig = await fetchTargetConfig(targetId);
    setConfig(targetConfig);
  }, []);

  const reloadPageData = useCallback(async (targetId: string, env: string) => {
    const [appsResponse, targetsResponse] = await Promise.all([
      fetchAvailableApps(),
      fetchTargets(env),
    ]);

    setAvailableApps(appsResponse.apps);

    const targets = targetsResponse.targets
      .filter(isWritableTarget)
      .map((target) => ({
        id: target.id,
        display_name: target.display_name ?? target.id,
      }));
    setWritableTargets(targets);

    const resolvedTargetId =
      targetId && targets.some((target) => target.id === targetId)
        ? targetId
        : (targets[0]?.id ?? "");

    if (resolvedTargetId) {
      setSelectedTargetId(resolvedTargetId);
      await loadTargetConfig(resolvedTargetId);
    } else {
      setSelectedTargetId("");
      setConfig(null);
    }
  }, [loadTargetConfig]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      setLoading(true);
      setError(null);

      try {
        const envs = await fetchEnvironments();
        const defaultEnv = envs[0]?.name ?? "test";
        setEnvironment(defaultEnv);
        const [appsResponse, targetsResponse] = await Promise.all([
          fetchAvailableApps(),
          fetchTargets(defaultEnv),
        ]);

        if (cancelled) {
          return;
        }

        setAvailableApps(appsResponse.apps);

        const targets = targetsResponse.targets
          .filter(isWritableTarget)
          .map((target) => ({
            id: target.id,
            display_name: target.display_name ?? target.id,
          }));
        setWritableTargets(targets);

        const firstTargetId = targets[0]?.id ?? "";
        setSelectedTargetId(firstTargetId);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load apps manager");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadInitial();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedTargetId || loading) {
      return;
    }

    let cancelled = false;

    async function loadConfig() {
      setError(null);
      try {
        const targetConfig = await fetchTargetConfig(selectedTargetId);
        if (!cancelled) {
          setConfig(targetConfig);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load target config");
        }
      }
    }

    loadConfig();

    return () => {
      cancelled = true;
    };
  }, [selectedTargetId, loading]);

  async function handleGitPull() {
    setPulling(true);
    setGitPullMessage(null);
    setError(null);

    try {
      const result = await fetchGitPull();
      if (result.success) {
        setGitPullMessage(result.message || "Git pull succeeded");
        await reloadPageData(selectedTargetId, environment);
      } else {
        setError(result.message || "Git pull failed");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Git pull failed");
    } finally {
      setPulling(false);
    }
  }

  async function runAppsUpdate(nextApps: TargetApp[]): Promise<void> {
    if (!selectedTargetId) {
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const updated = await updateTargetApps(selectedTargetId, nextApps);
      setConfig(updated);
      setShowApplyBanner(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update deployed apps");
    } finally {
      setSaving(false);
    }
  }

  async function runRemovalsUpdate(
    nextRemovals: TargetApp[],
  ): Promise<void> {
    if (!selectedTargetId) {
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const updated = await updateTargetRemovals(selectedTargetId, nextRemovals);
      setConfig(updated);
      setShowApplyBanner(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update removal list");
    } finally {
      setSaving(false);
    }
  }

  async function runRemoveActiveApp(appName: string): Promise<void> {
    if (!config || !selectedTargetId) {
      return;
    }

    const nextApps = config.apps.filter((app) => app.name !== appName);
    const nextRemovals = config.apps_to_remove.some((app) => app.name === appName)
      ? config.apps_to_remove
      : [...config.apps_to_remove, { name: appName }];

    setSaving(true);
    setError(null);

    try {
      await updateTargetApps(selectedTargetId, nextApps);
      const updated = await updateTargetRemovals(selectedTargetId, nextRemovals);
      setConfig(updated);
      setShowApplyBanner(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove app");
    } finally {
      setSaving(false);
    }
  }

  async function handleAddToDeploy(appName: string) {
    if (!config || !selectedTargetId) {
      return;
    }

    const pendingRemoval = config.apps_to_remove.some((app) => app.name === appName);
    const nextApps = [...config.apps, { name: appName }];

    if (!pendingRemoval) {
      void runAppsUpdate(nextApps);
      return;
    }

    const nextRemovals = config.apps_to_remove.filter((app) => app.name !== appName);

    setSaving(true);
    setError(null);

    try {
      await updateTargetRemovals(selectedTargetId, nextRemovals);
      const updated = await updateTargetApps(selectedTargetId, nextApps);
      setConfig(updated);
      setShowApplyBanner(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deploy app");
    } finally {
      setSaving(false);
    }
  }

  function handleRemoveFromDeploy(appName: string) {
    void runRemoveActiveApp(appName);
  }

  function handleCancelRemoval(appName: string) {
    if (!config) {
      return;
    }
    const nextRemovals = config.apps_to_remove.filter((app) => app.name !== appName);
    void runRemovalsUpdate(nextRemovals);
  }

  const configMatchesTarget =
    config !== null && config.target_id === selectedTargetId;
  const deployedNames = new Set(
    configMatchesTarget ? config.apps.map((app) => app.name) : [],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <span className="mr-3 inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Loading apps manager…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Apps Manager</h2>
          <p className="mt-1 text-sm text-slate-600">
            Manage deployed apps and removal lists per target. Changes commit and push
            automatically.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleGitPull()}
          disabled={pulling || saving}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pulling ? "Pulling…" : "Git Pull"}
        </button>
      </section>

      {gitPullMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {gitPullMessage}
        </div>
      )}

      {showApplyBanner && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-blue-900">
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm">
                Changes saved. Run the playbook to apply them to Splunk.
              </p>
              <Link
                to="/run"
                className="rounded-md bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800"
              >
                Go to Run Job
              </Link>
            </div>
            <button
              type="button"
              onClick={() => setShowApplyBanner(false)}
              className="rounded p-1 text-blue-700 hover:bg-blue-100"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          <p className="font-medium">Error</p>
          <p className="mt-1 text-sm">{error}</p>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-4">
        <label className="block text-sm">
          <span className="font-medium text-slate-700">Target</span>
          <select
            value={selectedTargetId}
            onChange={(event) => {
              setSelectedTargetId(event.target.value);
              setConfig(null);
            }}
            disabled={saving || writableTargets.length === 0}
            className="mt-1 block min-w-64 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            {writableTargets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.display_name}
              </option>
            ))}
          </select>
        </label>

        {config && (
          <p className="text-sm text-slate-500">
            Destination:{" "}
            <span className="font-mono text-xs text-slate-700">{config.destination}</span>
          </p>
        )}
      </div>

      {writableTargets.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-slate-500">
          No writable targets found.
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">Available Apps</h3>
            <p className="mt-1 text-sm text-slate-500">
              Directories under the apps path in the deployment repo.
            </p>

            {availableApps.length === 0 ? (
              <p className="mt-4 text-sm text-slate-600">
                No apps found in the apps directory. Add your Splunk app directories to the
                apps/ folder in your deployment config repository.
              </p>
            ) : (
              <ul className="mt-4 space-y-3">
                {availableApps.map((appName) => {
                  const isDeployed = deployedNames.has(appName);

                  return (
                    <li
                      key={appName}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
                    >
                      <span className="font-mono text-sm text-slate-800">{appName}</span>
                      <div className="flex flex-wrap items-center gap-2">
                        {isDeployed ? (
                          <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                            Deployed
                          </span>
                        ) : configMatchesTarget ? (
                          <button
                            type="button"
                            disabled={saving}
                            onClick={() => void handleAddToDeploy(appName)}
                            className="rounded-md bg-green-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            Deploy
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400">Loading…</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-900">Configured</h3>

            <div className="mt-4">
              <h4 className="text-sm font-medium text-slate-700">Active Apps</h4>
              {!config || config.apps.length === 0 ? (
                <p className="mt-2 text-sm text-slate-400">No active apps.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {config.apps.map((app) => (
                    <li
                      key={app.name}
                      className="flex items-center justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
                    >
                      <span className="font-mono text-sm text-slate-800">{app.name}</span>
                      <button
                        type="button"
                        disabled={saving}
                        onClick={() => handleRemoveFromDeploy(app.name)}
                        className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="mt-6">
              <h4 className="text-sm font-medium text-red-600">Pending Removal</h4>
              {!config || config.apps_to_remove.length === 0 ? (
                <p className="mt-2 text-sm text-slate-400">No apps pending removal.</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {config.apps_to_remove.map((app) => (
                    <li
                      key={app.name}
                      className="flex items-center justify-between gap-2 rounded-md border border-red-100 bg-red-50 px-3 py-2"
                    >
                      <span className="font-mono text-sm text-red-800 line-through">
                        {app.name}
                      </span>
                      <button
                        type="button"
                        disabled={saving}
                        onClick={() => handleCancelRemoval(app.name)}
                        className="rounded-md border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
