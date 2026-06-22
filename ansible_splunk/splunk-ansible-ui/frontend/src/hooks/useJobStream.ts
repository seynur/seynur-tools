import { useEffect, useState } from "react";

import { fetchJob, fetchJobOutput } from "../api/client";
import type { JobComplete, JobStatus, LogLine } from "../api/types";

function buildWebSocketUrl(jobId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/jobs/${jobId}/stream`;
}

function parseMessage(data: string): LogLine | JobComplete | null {
  try {
    const parsed: unknown = JSON.parse(data);
    if (typeof parsed !== "object" || parsed === null) {
      return null;
    }

    if ("type" in parsed && parsed.type === "log" && "line" in parsed) {
      return parsed as LogLine;
    }

    if ("status" in parsed && "exit_code" in parsed) {
      return parsed as JobComplete;
    }
  } catch {
    return null;
  }

  return null;
}

function isTerminalStatus(status: JobStatus): boolean {
  return status === "succeeded" || status === "failed";
}

export function useJobStream(jobId: string | null | undefined) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    const activeJobId = jobId;
    let cancelled = false;
    let socket: WebSocket | null = null;

    setLines([]);
    setStatus(null);
    setExitCode(null);
    setIsStreaming(true);

    async function loadCompletedJobOutput() {
      const [job, output] = await Promise.all([
        fetchJob(activeJobId),
        fetchJobOutput(activeJobId),
      ]);

      if (cancelled) {
        return;
      }

      setLines(output.lines);
      setStatus(job.status);
      setExitCode(job.exit_code);
      setIsStreaming(false);
    }

    async function start() {
      try {
        const job = await fetchJob(activeJobId);
        if (cancelled) {
          return;
        }

        if (isTerminalStatus(job.status)) {
          await loadCompletedJobOutput();
          return;
        }
      } catch {
        if (!cancelled) {
          setIsStreaming(false);
        }
        return;
      }

      socket = new WebSocket(buildWebSocketUrl(activeJobId));

      socket.onmessage = (event) => {
        const message = parseMessage(String(event.data));
        if (!message) {
          return;
        }

        if ("type" in message) {
          setLines((current) => [...current, message.line]);
          return;
        }

        setStatus(message.status);
        setExitCode(message.exit_code);
        setIsStreaming(false);
      };

      socket.onerror = async () => {
        if (cancelled) {
          return;
        }

        try {
          const job = await fetchJob(activeJobId);
          if (cancelled) {
            return;
          }

          if (isTerminalStatus(job.status)) {
            await loadCompletedJobOutput();
            return;
          }
        } catch {
          // Fall through to stop streaming state.
        }

        if (!cancelled) {
          setIsStreaming(false);
        }
      };

      socket.onclose = async () => {
        if (cancelled) {
          return;
        }

        try {
          const job = await fetchJob(activeJobId);
          if (cancelled) {
            return;
          }

          if (isTerminalStatus(job.status)) {
            await loadCompletedJobOutput();
            return;
          }
        } catch {
          // Fall through to stop streaming state.
        }

        if (!cancelled) {
          setIsStreaming(false);
        }
      };
    }

    void start();

    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [jobId]);

  return { lines, status, exitCode, isStreaming };
}
