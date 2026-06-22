import { useEffect, useRef } from "react";

import type { JobStatus } from "../api/types";

interface JobLogProps {
  lines: string[];
  status: JobStatus | null;
  exitCode: number | null;
  isStreaming: boolean;
}

export default function JobLog({
  lines,
  status,
  exitCode,
  isStreaming,
}: JobLogProps) {
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, isStreaming, status]);

  const isComplete = !isStreaming && status !== null;
  const succeeded = status === "succeeded";
  const failed = status === "failed";

  return (
    <div className="overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <span className="font-mono text-xs text-slate-400">ansible-playbook output</span>
        {isStreaming && (
          <div className="flex items-center gap-2 text-xs text-slate-300">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-slate-500 border-t-slate-200" />
            Streaming…
          </div>
        )}
        {isComplete && succeeded && (
          <span className="text-xs font-medium text-green-400">
            Succeeded{exitCode !== null ? ` (exit ${exitCode})` : ""}
          </span>
        )}
        {isComplete && failed && (
          <span className="text-xs font-medium text-red-400">
            Failed{exitCode !== null ? ` (exit ${exitCode})` : ""}
          </span>
        )}
      </div>

      <pre className="max-h-96 overflow-y-auto p-4 font-mono text-sm leading-relaxed text-slate-100">
        {lines.length > 0 ? (
          lines.map((line, index) => (
            <div key={`${index}-${line}`} className="whitespace-pre-wrap break-words">
              {line}
            </div>
          ))
        ) : (
          <span className="text-slate-500">
            {isStreaming ? "Waiting for output…" : "No output yet."}
          </span>
        )}
        <div ref={logEndRef} />
      </pre>
    </div>
  );
}
