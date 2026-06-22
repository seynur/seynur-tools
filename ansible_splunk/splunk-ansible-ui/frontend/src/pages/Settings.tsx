import { useEffect, useState } from "react";

import { fetchSettings, updateSettings } from "../api/client";
import type { Settings } from "../api/types";

const EMPTY_SETTINGS: Settings = {
  splunkapps_path: "",
  allowed_environments: "",
  allowed_playbooks: "",
  remote_user: "",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(EMPTY_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      setLoading(true);
      setError(null);
      setSuccessMessage(null);

      try {
        const data = await fetchSettings();
        if (!cancelled) {
          setSettings(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load settings");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  function updateField<K extends keyof Settings>(field: K, value: Settings[K]) {
    setSettings((current) => ({ ...current, [field]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updated = await updateSettings(settings);
      setSettings(updated);
      setSuccessMessage("Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <span className="mr-3 inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Loading settings…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">Settings</h2>
        <p className="mt-2 text-sm text-slate-600">
          Configure application behavior without editing environment files.
        </p>
      </section>

      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
        <p className="text-sm font-medium">Changes take effect immediately</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          <p className="text-sm">{error}</p>
        </div>
      )}

      {successMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-green-800">
          <p className="text-sm">{successMessage}</p>
        </div>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">SPLUNKAPPS_PATH</span>
          <input
            type="text"
            value={settings.splunkapps_path}
            onChange={(event) => updateField("splunkapps_path", event.target.value)}
            disabled={saving}
            placeholder="/opt/splunk/splunkapps"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm text-slate-900 disabled:bg-slate-50"
          />
        </label>

        <label className="mt-4 block">
          <span className="text-sm font-medium text-slate-700">ALLOWED_ENVIRONMENTS</span>
          <input
            type="text"
            value={settings.allowed_environments}
            onChange={(event) => updateField("allowed_environments", event.target.value)}
            disabled={saving}
            placeholder="test,docker-test"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm text-slate-900 disabled:bg-slate-50"
          />
          <span className="mt-1 block text-xs text-slate-500">
            Environments where Run Job is permitted. Must match inventory file names under
            inventory/.
          </span>
        </label>

        <label className="mt-4 block">
          <span className="text-sm font-medium text-slate-700">ALLOWED_PLAYBOOKS</span>
          <input
            type="text"
            value={settings.allowed_playbooks}
            onChange={(event) => updateField("allowed_playbooks", event.target.value)}
            disabled={saving}
            placeholder="git_client,fwd_deploymentserver"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm text-slate-900 disabled:bg-slate-50"
          />
          <span className="mt-1 block text-xs text-slate-500">Comma-separated playbook IDs</span>
        </label>

        <label className="mt-4 block md:max-w-md">
          <span className="text-sm font-medium text-slate-700">remote_user</span>
          <input
            type="text"
            value={settings.remote_user}
            onChange={(event) => updateField("remote_user", event.target.value)}
            disabled={saving}
            placeholder="splunk"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm text-slate-900 disabled:bg-slate-50"
          />
        </label>

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="mt-6 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </section>
    </div>
  );
}
