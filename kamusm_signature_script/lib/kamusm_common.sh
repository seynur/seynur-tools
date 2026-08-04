#!/usr/bin/env bash
#
# Shared helpers for KamuSM timestamp tooling.
# Sourced by kamusm_timestamp.sh — do not execute directly.
#
# Backend seam: set KAMUSM_BACKEND=jar (default) or mock before calling
# stamp_file / verify_token.

# shellcheck disable=SC2034  # config vars consumed by callers

: "${KAMUSM_BACKEND:=jar}"
: "${TSA_URL:=http://tzd.kamusm.gov.tr}"
: "${TSA_PORT:=80}"
: "${HASH_ALG:=sha-256}"
: "${CUSTOMER_NO:=${KAMUSM_CUSTOMER_NO:-}}"
: "${CUSTOMER_PASSWORD:=${KAMUSM_CUSTOMER_PASSWORD:-}}"

# Bucket store subdirs under each index that may hold warm/cold/thawed buckets.
readonly KAMUSM_BUCKET_SUBDIRS="db colddb thaweddb"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

log() {
  echo "$*"
}

log_err() {
  echo "$*" >&2
}

require_cmds() {
  local missing=() bin
  for bin in "$@"; do
    command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    die "missing required tool(s): ${missing[*]}"
  fi
}

hex_encode() {
  local file="$1"
  if command -v xxd >/dev/null 2>&1; then
    xxd -p "$file" | tr -d '\n'
  else
    od -An -v -tx1 "$file" | tr -d ' \n'
  fi
}

# Path: .../<index>/{db|colddb|thaweddb}/<bucket_id>
bucket_id_from_path() {
  basename "$1"
}

token_path() {
  local kamusmdb="$1" index="$2" bucket_id="$3"
  printf '%s/%s/%s.zd' "$kamusmdb" "$index" "$bucket_id"
}

ledger_path() {
  local kamusmdb="$1"
  printf '%s/ledger.csv' "$kamusmdb"
}

find_l2_hash_file() {
  local bucket_dir="$1"
  local rawdata="$bucket_dir/rawdata"
  [[ -d "$rawdata" ]] || return 1
  # Prefer a stable first match; only l2Hash (batch mode ignores l1Hashes).
  find "$rawdata" -maxdepth 1 -type f -iname 'l2Hash_*.dat' 2>/dev/null | sort | head -1
}

# Print lines: index<TAB>bucket_id<TAB>bucket_path
# Optional second arg filters to a single index name.
iter_l2_buckets() {
  local splunkdb="$1"
  local index_filter="${2:-}"
  local index_dir index_name subdir bucket_dir hash_file

  [[ -d "$splunkdb" ]] || die "SPLUNKDB does not exist: $splunkdb"

  if [[ -n "$index_filter" ]]; then
    index_dir="$splunkdb/$index_filter"
    [[ -d "$index_dir" ]] || die "index directory not found: $index_dir"
    _emit_l2_buckets_for_index "$index_dir" "$index_filter"
    return 0
  fi

  for index_dir in "$splunkdb"/*/; do
    [[ -d "$index_dir" ]] || continue
    index_name="$(basename "$index_dir")"
    # Skip non-index clutter at top level if any
    _emit_l2_buckets_for_index "$index_dir" "$index_name"
  done
}

_emit_l2_buckets_for_index() {
  local index_dir="$1"
  local index_name="$2"
  local subdir bucket_dir hash_file bucket_id

  for subdir in $KAMUSM_BUCKET_SUBDIRS; do
    [[ -d "$index_dir/$subdir" ]] || continue
    for bucket_dir in "$index_dir/$subdir"/*/; do
      [[ -d "$bucket_dir" ]] || continue
      bucket_dir="${bucket_dir%/}"
      hash_file="$(find_l2_hash_file "$bucket_dir" || true)"
      [[ -n "$hash_file" ]] || continue
      bucket_id="$(bucket_id_from_path "$bucket_dir")"
      printf '%s\t%s\t%s\n' "$index_name" "$bucket_id" "$bucket_dir"
    done
  done
}

# Print lines: index<TAB>bucket_id<TAB>token_path
iter_timestamp_tokens() {
  local kamusmdb="$1"
  local index_filter="${2:-}"
  local index_dir index_name token bucket_id

  [[ -d "$kamusmdb" ]] || return 0

  if [[ -n "$index_filter" ]]; then
    index_dir="$kamusmdb/$index_filter"
    [[ -d "$index_dir" ]] || return 0
    _emit_tokens_for_index "$index_dir" "$index_filter"
    return 0
  fi

  for index_dir in "$kamusmdb"/*/; do
    [[ -d "$index_dir" ]] || continue
    index_name="$(basename "$index_dir")"
    _emit_tokens_for_index "$index_dir" "$index_name"
  done
}

_emit_tokens_for_index() {
  local index_dir="$1"
  local index_name="$2"
  local token bucket_id

  for token in "$index_dir"/*.zd; do
    [[ -f "$token" ]] || continue
    bucket_id="$(basename "$token" .zd)"
    printf '%s\t%s\t%s\n' "$index_name" "$bucket_id" "$token"
  done
}

append_ledger() {
  local kamusmdb="$1"
  local timestamp_utc="$2"
  local index="$3"
  local bucket_id="$4"
  local hash_kind="$5"
  local hash_hex="$6"
  local hash_file="$7"
  local token_file="$8"
  local ledger
  ledger="$(ledger_path "$kamusmdb")"

  mkdir -p "$kamusmdb"
  if [[ ! -f "$ledger" ]]; then
    echo "timestamp_utc,index,bucket_id,hash_kind,hash,hash_file,token_file" >"$ledger"
  fi
  echo "${timestamp_utc},${index},${bucket_id},${hash_kind},${hash_hex},${hash_file},${token_file}" >>"$ledger"
}

# ---------------------------------------------------------------------------
# Backend: stamp_file / verify_token
# stamp_file HASH_FILE DEST_ZD — writes the token at DEST_ZD via temp-then-mv.
# Never writes into the directory that holds HASH_FILE (Splunk buckets stay
# read-only). A failed stamp leaves any prior DEST_ZD intact.
# ---------------------------------------------------------------------------

_mock_marker_for_file() {
  local hash_file="$1"
  local digest
  digest="$(hex_encode "$hash_file")"
  printf 'MOCK-ZD:%s\n' "$digest"
}

# stamp_file HASH_FILE DEST_ZD
# Produces the timestamp token directly at DEST_ZD. Never writes into the
# directory that holds HASH_FILE, so Splunk bucket directories stay read-only.
stamp_file() {
  local hash_file="$1"
  local dest_zd="$2"
  case "$KAMUSM_BACKEND" in
    mock) _stamp_file_mock "$hash_file" "$dest_zd" ;;
    jar)  _stamp_file_jar "$hash_file" "$dest_zd" ;;
    *)    die "unknown KAMUSM_BACKEND='$KAMUSM_BACKEND' (use jar or mock)" ;;
  esac
}

verify_token() {
  local hash_file="$1"
  local zd_file="$2"
  case "$KAMUSM_BACKEND" in
    mock) _verify_token_mock "$hash_file" "$zd_file" ;;
    jar)  _verify_token_jar "$hash_file" "$zd_file" ;;
    *)    die "unknown KAMUSM_BACKEND='$KAMUSM_BACKEND' (use jar or mock)" ;;
  esac
}

_stamp_file_mock() {
  local hash_file="$1"
  local dest_zd="$2"
  local tmp
  mkdir -p "$(dirname "$dest_zd")"
  tmp="${dest_zd}.tmp.$$"
  _mock_marker_for_file "$hash_file" >"$tmp"
  mv -f -- "$tmp" "$dest_zd"
}

_verify_token_mock() {
  local hash_file="$1"
  local zd_file="$2"
  local expected actual

  [[ -f "$zd_file" ]] || return 1
  # Allow tests to force failure with a sibling marker or BAD content.
  if [[ -f "${zd_file}.bad" ]] || grep -q '^MOCK-ZD-BAD' "$zd_file" 2>/dev/null; then
    return 1
  fi
  expected="$(_mock_marker_for_file "$hash_file")"
  actual="$(cat "$zd_file")"
  [[ "$actual" == "$expected" ]]
}

_stamp_file_jar() {
  local hash_file="$1"
  local dest_zd="$2"

  [[ -n "$CUSTOMER_NO" && -n "$CUSTOMER_PASSWORD" ]] || {
    log_err "KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD are not set"
    return 1
  }
  [[ -f "$JAR_PATH" ]] || {
    log_err "Zamane console jar not found at: $JAR_PATH"
    return 1
  }

  # The Zamane jar writes its token as <input>.zd next to the input file.
  # To avoid writing anything into the Splunk bucket directory, copy the hash
  # file into a private scratch dir, stamp the copy there, then move the token
  # to DEST_ZD. The token is over the file CONTENT (RFC 3161 message imprint),
  # so verifying later against the original hash_file still succeeds.
  local work in out rc=0 msg=""
  work="$(mktemp -d "${TMPDIR:-/tmp}/kamusm.XXXXXX")" || {
    log_err "could not create scratch dir for stamping"
    return 1
  }
  in="$work/$(basename "$hash_file")"
  out="${in}.zd"

  if ! cp -p -- "$hash_file" "$in"; then
    msg="could not copy hash file to scratch: $hash_file"; rc=1
  elif ! java -jar "$JAR_PATH" -ZC "$in" "$TSA_URL" "$TSA_PORT" \
      "$CUSTOMER_NO" "$CUSTOMER_PASSWORD" "$HASH_ALG"; then
    msg="Zamane client stamp failed for: $hash_file"; rc=1
  elif [[ ! -f "$out" ]]; then
    msg="expected token file not found: $out"; rc=1
  else
    mkdir -p "$(dirname "$dest_zd")"
    if ! mv -f -- "$out" "$dest_zd"; then
      msg="could not move token to: $dest_zd"; rc=1
    fi
  fi

  rm -rf "$work"
  [[ "$rc" -eq 0 ]] || log_err "$msg"
  return "$rc"
}

_verify_token_jar() {
  local hash_file="$1"
  local zd_file="$2"

  [[ -f "$JAR_PATH" ]] || die "Zamane console jar not found at: $JAR_PATH"
  java -jar "$JAR_PATH" -CC "$hash_file" "$zd_file"
}

require_jar_backend_prereqs() {
  require_cmds java find basename dirname sort head mkdir mv cat cp mktemp
  [[ -f "$JAR_PATH" ]] || die "Zamane console jar not found at: $JAR_PATH
Download it or set KAMUSM_JAR_PATH:
https://kamusm.bilgem.tubitak.gov.tr/urunler/zaman_damgasi/ucretsiz_zaman_damgasi_istemci_yazilimi.jsp"
  [[ -n "$CUSTOMER_NO" && -n "$CUSTOMER_PASSWORD" ]] || \
    die "KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD are not set.
export KAMUSM_CUSTOMER_NO=9207
export KAMUSM_CUSTOMER_PASSWORD='...'"
}

require_mock_backend_prereqs() {
  require_cmds find basename dirname sort head mkdir mv cat
}