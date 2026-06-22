import type { Environment } from "../api/types";

interface EnvironmentBadgeProps {
  environment: Environment;
}

export default function EnvironmentBadge({ environment }: EnvironmentBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
        environment.runnable
          ? "bg-green-100 text-green-800"
          : "bg-slate-100 text-slate-600"
      }`}
    >
      {environment.name}
    </span>
  );
}
