import { useEffect, useState } from "react";

import { fetchJob, fetchJobs } from "../api/client";
import type { Job } from "../api/types";
import JobLog from "../components/JobLog";
import { useJobStream } from "../hooks/useJobStream";

function formatDuration(job: Job): string {
  if (!job.finished_at) {
    return job.status === "running" ? "running…" : "—";
  }

  const seconds = Math.round(
    (new Date(job.finished_at).getTime() - new Date(job.created_at).getTime()) / 1000,
  );

  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}m ${remainder}s`;
}

function formatCreatedAt(createdAt: string): string {
  return new Date(createdAt).toLocaleString();
}

function statusClass(status: Job["status"]): string {
  switch (status) {
    case "succeeded":
      return "bg-green-100 text-green-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "running":
      return "bg-blue-100 text-blue-800";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

export default function JobHistory() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingLog, setLoadingLog] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { lines, status, exitCode, isStreaming } = useJobStream(selectedJobId);

  useEffect(() => {
    let cancelled = false;

    async function loadJobs() {
      setLoading(true);
      setError(null);

      try {
        const data = await fetchJobs();
        if (!cancelled) {
          setJobs(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load jobs");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadJobs();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSelectJob(jobId: string) {
    setLoadingLog(true);
    setError(null);
    setSelectedJobId(null);
    setSelectedJob(null);

    try {
      const job = await fetchJob(jobId);
      setSelectedJob(job);
      setSelectedJobId(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
    } finally {
      setLoadingLog(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-slate-500">
        <span className="mr-3 inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        Loading job history…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-2xl font-semibold text-slate-900">Job History</h2>
        <p className="mt-2 text-sm text-slate-600">
          Session jobs stored in memory on the API server.
        </p>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          <p className="text-sm">{error}</p>
        </div>
      )}

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        {jobs.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No jobs yet.</p>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Playbook</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Environment</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Duration</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => handleSelectJob(job.id)}
                  className={`cursor-pointer hover:bg-slate-50 ${
                    selectedJobId === job.id ? "bg-slate-100" : ""
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-xs">{job.playbook}</td>
                  <td className="px-4 py-3">{job.environment}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusClass(job.status)}`}
                    >
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{formatDuration(job)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatCreatedAt(job.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {loadingLog && (
        <div className="text-sm text-slate-500">Loading job log…</div>
      )}

      {selectedJob && (
        <section>
          <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
            Log — {selectedJob.playbook} ({selectedJob.environment})
          </h3>
          <JobLog
            lines={lines}
            status={status ?? selectedJob.status}
            exitCode={exitCode ?? selectedJob.exit_code}
            isStreaming={isStreaming}
          />
        </section>
      )}
    </div>
  );
}
