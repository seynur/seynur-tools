#!/usr/bin/env bash
#
# kamusm_run.sh — scheduler-friendly wrapper around kamusm_timestamp.sh
#
# Usage:
#   kamusm_run.sh create [extra args passed to signer]
#   kamusm_run.sh verify [--strict-coverage ...]
#
# Reads configuration from kamusm.env (next to this script, or $KAMUSM_ENV_FILE).
# Safe to run on a short interval: the signer is idempotent (buckets that
# already have a .zd token are skipped), and a per-mode flock prevents
# overlapping runs on the same host.
#
# Exit code is the worst exit code across the per-index signer invocations,
# so cron/monitoring can alert on non-zero.
#
set -euo pipefail

MODE="${1:-}"
[[ $# -ge 1 ]] && shift || true
case "$MODE" in
  create|verify) ;;
  *) echo "usage: $0 {create|verify} [extra signer args]" >&2; exit 2 ;;
esac

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${KAMUSM_ENV_FILE:-$SELF_DIR/kamusm.env}"
if [[ ! -r "$ENV_FILE" ]]; then
  echo "ERROR: env file not readable: $ENV_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

# --- required config --------------------------------------------------------
: "${SIGNER:?set SIGNER in $ENV_FILE}"
: "${SPLUNKDB:?set SPLUNKDB in $ENV_FILE}"
: "${KAMUSMDB:?set KAMUSMDB in $ENV_FILE}"
: "${INDEXES:=ALL}"
: "${LOG_DIR:=/var/log/kamusm}"
: "${LOCK_DIR:=/var/run}"

[[ -x "$SIGNER" ]] || { echo "ERROR: SIGNER not executable: $SIGNER" >&2; exit 1; }
[[ -d "$SPLUNKDB" ]] || { echo "ERROR: SPLUNKDB missing: $SPLUNKDB" >&2; exit 1; }

# --- export what the signer / jar expect ------------------------------------
export KAMUSM_CUSTOMER_NO KAMUSM_CUSTOMER_PASSWORD KAMUSM_JAR_PATH \
       KAMUSM_TSA_URL KAMUSM_TSA_PORT KAMUSM_HASH_ALG KAMUSM_BACKEND
[[ -n "${EXTRA_PATH:-}" ]] && export PATH="$EXTRA_PATH:$PATH"

mkdir -p "$LOG_DIR" "$LOCK_DIR"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
HOST="$(hostname -s 2>/dev/null || hostname)"
LOG_FILE="$LOG_DIR/${MODE}-$(date -u +%Y%m%d).log"
SUMMARY_LOG="$LOG_DIR/kamusm_summary.log"

# --- single instance per (host, mode) ---------------------------------------
LOCK_FILE="$LOCK_DIR/kamusm-${MODE}.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(ts) [$MODE] previous run still active on $HOST; skipping" >>"$LOG_FILE"
  exit 0
fi

run_signer() {  # $1 = index name or empty for all
  local idx="$1"; shift
  if [[ -n "$idx" ]]; then
    "$SIGNER" "$MODE" --splunkdb "$SPLUNKDB" --kamusmdb "$KAMUSMDB" \
      --index "$idx" "$@"
  else
    "$SIGNER" "$MODE" --splunkdb "$SPLUNKDB" --kamusmdb "$KAMUSMDB" "$@"
  fi
}

rc=0
{
  echo "===== $(ts) $MODE start host=$HOST splunkdb=$SPLUNKDB kamusmdb=$KAMUSMDB ====="
  if [[ "$INDEXES" == "ALL" ]]; then
    run_signer "" "$@" || rc=$?
  else
    for idx in $INDEXES; do
      echo "----- $(ts) $MODE index=$idx -----"
      run_signer "$idx" "$@" || rc=$?
    done
  fi
  echo "===== $(ts) $MODE end host=$HOST rc=$rc ====="
} >>"$LOG_FILE" 2>&1

# Structured one-liner for easy Splunk ingestion / alerting.
echo "$(ts) kamusm_run host=$HOST mode=$MODE indexes=\"$INDEXES\" rc=$rc log=$LOG_FILE" \
  | tee -a "$SUMMARY_LOG" >>"$LOG_FILE"

exit "$rc"