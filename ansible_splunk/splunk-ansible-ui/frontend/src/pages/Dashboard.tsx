import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchEnvironments, fetchGitStatus, fetchTargets } from "../api/client";
import type { Environment, Target } from "../api/types";
import EnvironmentBadge from "../components/EnvironmentBadge";
import TargetCard from "../components/TargetCard";

export default function Dashboard() {
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [targets, setTargets] = useState<Target[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uncommittedFiles, setUncommittedFiles] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError(null);

      try {
        const [envs, targetsResponse, gitStatus] = await Promise.all([
          fetchEnvironments(),
          fetchTargets("test"),
          fetchGitStatus(),
        ]);

        if (cancelled) {
          return;
        }

        setEnvironments(envs);
        setTargets(targetsResponse.targets);
        setUncommittedFiles(gitStatus.files);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, []);

  const visibleEnvironments = environments.filter((env) => env.runnable);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <span className="mr-3 inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Loading dashboard…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
        <p className="font-medium">Failed to load dashboard</p>
        <p className="mt-1 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">Dashboard</h2>
      </section>

      {uncommittedFiles.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
          <p className="text-sm">
            Uncommitted changes in deployment config: {uncommittedFiles.join(", ")}.{" "}
            <Link to="/apps" className="font-medium underline hover:text-amber-950">
              Go to Apps
            </Link>
          </p>
        </div>
      )}

      <section>
        <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
          Environments
        </h3>
        <div className="flex flex-wrap gap-2">
          {visibleEnvironments.map((environment) => (
            <EnvironmentBadge key={environment.name} environment={environment} />
          ))}
        </div>
      </section>

      <section>
        <h3 className="mb-4 text-sm font-medium uppercase tracking-wide text-slate-500">
          Targets (test)
        </h3>
        <div className="grid gap-4 md:grid-cols-2">
          {targets.map((target) => (
            <TargetCard key={target.id} target={target} />
          ))}
        </div>
      </section>
    </div>
  );
}
