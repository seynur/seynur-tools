#!/usr/bin/env bash
#
# kamusm_timestamp.sh
#
# Batch-create and verify KamuSM (Zamane) timestamps for Splunk warm/cold
# buckets that have Data Integrity Control l2Hash files.
#
# Tokens are stored under KAMUSMDB as:
#   $KAMUSMDB/<index>/<bucket_id>.zd
# Ledger (audit only):
#   $KAMUSMDB/ledger.csv
#
# Usage:
#   kamusm_timestamp.sh create  --splunkdb DIR --kamusmdb DIR [--index NAME] [--dry-run] [--force]
#   kamusm_timestamp.sh verify  --splunkdb DIR --kamusmdb DIR [--index NAME] [--strict-coverage]
#
# Environment:
#   KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD  (required for jar backend)
#   KAMUSM_JAR_PATH     path to tss-client-console-*.jar
#   KAMUSM_BACKEND      jar (default) | mock
#   KAMUSM_TSA_URL / KAMUSM_TSA_PORT / KAMUSM_HASH_ALG
#
# SECURITY NOTE: the jar accepts the password as a CLI argument (visible via ps).
# Run only on hosts where that risk is acceptable, or under a locked-down account.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/kamusm_common.sh
source "$SCRIPT_DIR/lib/kamusm_common.sh"

TSA_URL="${KAMUSM_TSA_URL:-http://tzd.kamusm.gov.tr}"
TSA_PORT="${KAMUSM_TSA_PORT:-80}"
HASH_ALG="${KAMUSM_HASH_ALG:-sha-256}"
CUSTOMER_NO="${KAMUSM_CUSTOMER_NO:-}"
CUSTOMER_PASSWORD="${KAMUSM_CUSTOMER_PASSWORD:-}"
JAR_PATH="${KAMUSM_JAR_PATH:-$SCRIPT_DIR/tss-client-console-3.1.33.jar}"
KAMUSM_BACKEND="${KAMUSM_BACKEND:-jar}"

usage() {
  cat >&2 <<EOF
Usage:
  $0 create  --splunkdb DIR --kamusmdb DIR [--index NAME] [--dry-run] [--force]
  $0 verify  --splunkdb DIR --kamusmdb DIR [--index NAME] [--strict-coverage]
  $0 --help

Commands:
  create   Timestamp unstamped buckets that have l2Hash files
  verify   Verify existing .zd tokens; report unstamped / failed buckets

Options:
  --splunkdb DIR       Splunk DB root (e.g. /opt/splunk/var/lib/splunk)
  --kamusmdb DIR       Timestamp store root (e.g. /opt/kamusmsignatures)
  --index NAME         Limit to one index
  --dry-run            (create) list buckets to stamp; do not call backend
  --force              (create) re-stamp buckets that already have a .zd
  --strict-coverage    (verify) fail if any l2Hash bucket lacks a .zd

Environment:
  KAMUSM_BACKEND=jar|mock   (default: jar; mock needs no credentials)
  KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD / KAMUSM_JAR_PATH
EOF
  exit 1
}

preflight() {
  case "$KAMUSM_BACKEND" in
    mock) require_mock_backend_prereqs ;;
    jar)  require_jar_backend_prereqs ;;
    *)    die "unknown KAMUSM_BACKEND='$KAMUSM_BACKEND' (use jar or mock)" ;;
  esac
}

# Write sorted key lists (index/bucket_id) for set operations via comm.
_list_l2_keys() {
  local splunkdb="$1" index_filter="${2:-}"
  iter_l2_buckets "$splunkdb" "$index_filter" \
    | awk -F'\t' '{print $1 "/" $2}' \
    | sort -u
}

_list_token_keys() {
  local kamusmdb="$1" index_filter="${2:-}"
  iter_timestamp_tokens "$kamusmdb" "$index_filter" \
    | awk -F'\t' '{print $1 "/" $2}' \
    | sort -u
}

# Resolve bucket_path and hash_file for index/bucket_id; prints:
#   bucket_path<TAB>hash_file
_resolve_bucket() {
  local splunkdb="$1" index="$2" bucket_id="$3"
  local line bucket_path hash_file

  while IFS=$'\t' read -r idx bid bpath; do
    if [[ "$idx" == "$index" && "$bid" == "$bucket_id" ]]; then
      hash_file="$(find_l2_hash_file "$bpath" || true)"
      [[ -n "$hash_file" ]] || return 1
      printf '%s\t%s\n' "$bpath" "$hash_file"
      return 0
    fi
  done < <(iter_l2_buckets "$splunkdb" "$index")
  return 1
}

cmd_create() {
  local splunkdb="" kamusmdb="" index_filter="" dry_run=0 force=0
  local key index bucket_id resolved bucket_path hash_file dest jar_out
  local stamped=0 skipped=0 failed=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --splunkdb) [[ $# -ge 2 ]] || usage; splunkdb="$2"; shift 2 ;;
      --kamusmdb) [[ $# -ge 2 ]] || usage; kamusmdb="$2"; shift 2 ;;
      --index)    [[ $# -ge 2 ]] || usage; index_filter="$2"; shift 2 ;;
      --dry-run)  dry_run=1; shift ;;
      --force)    force=1; shift ;;
      -h|--help)  usage ;;
      *) die "unknown create option: $1" ;;
    esac
  done

  [[ -n "$splunkdb" && -n "$kamusmdb" ]] || usage
  [[ -d "$splunkdb" ]] || die "SPLUNKDB does not exist: $splunkdb"
  mkdir -p "$kamusmdb"

  if [[ "$dry_run" -eq 0 ]]; then
    preflight
  else
    require_cmds find basename dirname sort head mkdir comm
  fi

  local tmp_l2 tmp_tok tmp_diff
  tmp_l2="$(mktemp)"
  tmp_tok="$(mktemp)"
  tmp_diff="$(mktemp)"

  _list_l2_keys "$splunkdb" "$index_filter" >"$tmp_l2"
  _list_token_keys "$kamusmdb" "$index_filter" >"$tmp_tok"

  if [[ "$force" -eq 1 ]]; then
    # Re-stamp every l2 bucket
    cp "$tmp_l2" "$tmp_diff"
  else
    # B − A: l2 buckets without a token
    comm -23 "$tmp_l2" "$tmp_tok" >"$tmp_diff"
  fi

  # Count already-stamped skips (only when not forcing)
  if [[ "$force" -eq 0 ]]; then
    skipped="$(comm -12 "$tmp_l2" "$tmp_tok" | grep -c . || true)"
  fi

  if [[ ! -s "$tmp_diff" ]]; then
    log "Nothing to stamp."
    log "  skipped (already stamped): $skipped"
    rm -f "$tmp_l2" "$tmp_tok" "$tmp_diff"
    return 0
  fi

  local count_to_stamp
  count_to_stamp="$(grep -c . "$tmp_diff" || true)"
  log "Buckets to stamp: $count_to_stamp"
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    log "  $key"
  done <"$tmp_diff"

  if [[ "$dry_run" -eq 1 ]]; then
    log "Dry-run: no timestamps requested."
    rm -f "$tmp_l2" "$tmp_tok" "$tmp_diff"
    return 0
  fi

  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    index="${key%%/*}"
    bucket_id="${key#*/}"

    if ! resolved="$(_resolve_bucket "$splunkdb" "$index" "$bucket_id")"; then
      log_err "FAIL: could not resolve bucket $key"
      failed=$((failed + 1))
      continue
    fi
    # resolved = bucket_path<TAB>hash_file
    bucket_path="${resolved%%	*}"
    hash_file="${resolved#*	}"
    dest="$(token_path "$kamusmdb" "$index" "$bucket_id")"
    jar_out="${hash_file}.zd"

    mkdir -p "$(dirname "$dest")"
    rm -f "$jar_out"

    if ! stamp_file "$hash_file"; then
      log_err "FAIL: stamp failed for $key"
      failed=$((failed + 1))
      continue
    fi
    if [[ ! -f "$jar_out" ]]; then
      log_err "FAIL: token not produced for $key ($jar_out)"
      failed=$((failed + 1))
      continue
    fi

    mv "$jar_out" "$dest"
    append_ledger "$kamusmdb" "$(date -u +%Y%m%dT%H%M%SZ)" \
      "$index" "$bucket_id" "l2Hash" "$(hex_encode "$hash_file")" \
      "$hash_file" "$dest"
    log "OK: stamped $key -> $dest"
    stamped=$((stamped + 1))
  done <"$tmp_diff"

  rm -f "$tmp_l2" "$tmp_tok" "$tmp_diff"

  log ""
  log "Summary (create):"
  log "  stamped: $stamped"
  log "  skipped: $skipped"
  log "  failed:  $failed"

  [[ "$failed" -eq 0 ]] || return 1
  return 0
}

cmd_verify() {
  local splunkdb="" kamusmdb="" index_filter="" strict=0
  local key index bucket_id resolved bucket_path hash_file dest
  local verify_ok=0 verify_failed=0 unstamped=0 orphans=0
  local -a unstamped_list=() failed_list=() orphan_list=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --splunkdb)         [[ $# -ge 2 ]] || usage; splunkdb="$2"; shift 2 ;;
      --kamusmdb)         [[ $# -ge 2 ]] || usage; kamusmdb="$2"; shift 2 ;;
      --index)            [[ $# -ge 2 ]] || usage; index_filter="$2"; shift 2 ;;
      --strict-coverage)  strict=1; shift ;;
      -h|--help)          usage ;;
      *) die "unknown verify option: $1" ;;
    esac
  done

  [[ -n "$splunkdb" && -n "$kamusmdb" ]] || usage
  [[ -d "$splunkdb" ]] || die "SPLUNKDB does not exist: $splunkdb"
  preflight

  local tmp_l2 tmp_tok
  tmp_l2="$(mktemp)"
  tmp_tok="$(mktemp)"

  _list_l2_keys "$splunkdb" "$index_filter" >"$tmp_l2"
  _list_token_keys "$kamusmdb" "$index_filter" >"$tmp_tok"

  # Verify each l2 bucket
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    index="${key%%/*}"
    bucket_id="${key#*/}"
    dest="$(token_path "$kamusmdb" "$index" "$bucket_id")"

    if [[ ! -f "$dest" ]]; then
      unstamped=$((unstamped + 1))
      unstamped_list+=("$key")
      continue
    fi

    if ! resolved="$(_resolve_bucket "$splunkdb" "$index" "$bucket_id")"; then
      verify_failed=$((verify_failed + 1))
      failed_list+=("$key (unresolvable)")
      continue
    fi
    hash_file="${resolved#*$'\t'}"

    if verify_token "$hash_file" "$dest"; then
      verify_ok=$((verify_ok + 1))
    else
      verify_failed=$((verify_failed + 1))
      failed_list+=("$key")
    fi
  done <"$tmp_l2"

  # Orphans: tokens without matching l2 bucket
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    if ! grep -qxF "$key" "$tmp_l2"; then
      orphans=$((orphans + 1))
      orphan_list+=("$key")
    fi
  done <"$tmp_tok"

  if [[ ${#failed_list[@]} -gt 0 ]]; then
    log "verify_failed:"
    for key in "${failed_list[@]}"; do
      log "  $key"
    done
  fi
  if [[ ${#unstamped_list[@]} -gt 0 ]]; then
    log "unstamped:"
    for key in "${unstamped_list[@]}"; do
      log "  $key"
    done
  fi
  if [[ ${#orphan_list[@]} -gt 0 ]]; then
    log "orphan_tokens (info):"
    for key in "${orphan_list[@]}"; do
      log "  $key"
    done
  fi

  log ""
  log "Summary (verify):"
  log "  verify_ok:     $verify_ok"
  log "  verify_failed: $verify_failed"
  log "  unstamped:     $unstamped"
  log "  orphan_tokens: $orphans"

  if [[ "$verify_failed" -eq 0 ]]; then
    if [[ "$unstamped" -eq 0 ]]; then
      log "passed"
    else
      log "passed (with unstamped buckets)"
    fi
  fi

  rm -f "$tmp_l2" "$tmp_tok"

  [[ "$verify_failed" -eq 0 ]] || return 1
  if [[ "$strict" -eq 1 && "$unstamped" -gt 0 ]]; then
    log_err "strict-coverage: $unstamped unstamped bucket(s)"
    return 1
  fi
  return 0
}

main() {
  [[ $# -ge 1 ]] || usage
  local cmd="$1"
  shift

  case "$cmd" in
    create)  cmd_create "$@" ;;
    verify)  cmd_verify "$@" ;;
    -h|--help) usage ;;
    *) die "unknown command: $cmd (use create or verify)" ;;
  esac
}

main "$@"
