import type { Target } from "../api/types";

interface TargetCardProps {
  target: Target;
}

export default function TargetCard({ target }: TargetCardProps) {
  const title = target.display_name ?? target.playbook;

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          <p className="mt-0.5 font-mono text-xs text-slate-500">{target.playbook}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            target.runnable
              ? "bg-green-100 text-green-800"
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {target.runnable ? "Runnable" : "Read-only"}
        </span>
      </div>

      <dl className="space-y-3 text-sm text-slate-700">
        <div>
          <dt className="font-medium text-slate-500">Hosts</dt>
          <dd className="mt-1">
            {target.hosts.length > 0 ? (
              <ul className="list-inside list-disc">
                {target.hosts.map((host) => (
                  <li key={host}>{host}</li>
                ))}
              </ul>
            ) : (
              <span className="text-slate-400">No hosts configured</span>
            )}
          </dd>
        </div>

        <div>
          <dt className="font-medium text-slate-500">Destination</dt>
          <dd className="mt-1 font-mono text-xs">
            {target.destination ?? (
              <span className="text-slate-400">—</span>
            )}
          </dd>
        </div>

        <div>
          <dt className="font-medium text-slate-500">Apps</dt>
          <dd className="mt-1">
            {target.apps.length > 0 ? (
              <ul className="flex flex-wrap gap-1.5">
                {target.apps.map((app) => (
                  <li
                    key={app.name}
                    className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700"
                  >
                    {app.name}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-slate-400">No apps</span>
            )}
          </dd>
        </div>

        {target.apps_to_remove.length > 0 && (
          <div>
            <dt className="font-medium text-red-600">Apps marked for removal</dt>
            <dd className="mt-1">
              <ul className="flex flex-wrap gap-1.5">
                {target.apps_to_remove.map((app) => (
                  <li
                    key={app.name}
                    className="rounded border border-red-200 bg-red-50 px-2 py-0.5 font-mono text-xs text-red-700 line-through"
                  >
                    {app.name}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}
