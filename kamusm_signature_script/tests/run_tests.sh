#!/usr/bin/env bash
#
# Mock-backend tests for kamusm_timestamp.sh (no network, no real jar).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI="$ROOT/kamusm_timestamp.sh"
export KAMUSM_BACKEND=mock

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected='$expected' actual='$actual')" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_file() {
  local label="$1" path="$2"
  if [[ -f "$path" ]]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (missing $path)" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_no_file() {
  local label="$1" path="$2"
  if [[ ! -f "$path" ]]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (unexpected $path)" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local label="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (missing '$needle' in output)" >&2
    echo "$haystack" >&2
    FAIL=$((FAIL + 1))
  fi
}

assert_not_contains() {
  local label="$1" haystack="$2" needle="$3"
  if [[ "$haystack" != *"$needle"* ]]; then
    echo "  PASS: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (unexpected '$needle')" >&2
    FAIL=$((FAIL + 1))
  fi
}

run_cli() {
  # Runs CLI; sets RUN_OUT and RUN_RC (does not exit on non-zero).
  set +e
  RUN_OUT="$("$CLI" "$@" 2>&1)"
  RUN_RC=$?
  set -e
}

build_fixtures() {
  local base="$1"
  local splunkdb="$base/splunkdb"
  local kamusmdb="$base/kamusmdb"

  rm -rf "$base"
  mkdir -p \
    "$splunkdb/firewall/db/db_100_90_0/rawdata" \
    "$splunkdb/firewall/db/db_200_190_1/rawdata" \
    "$splunkdb/firewall/db/hot_v1_0/rawdata" \
    "$splunkdb/other/db/db_1_0_0/rawdata" \
    "$kamusmdb/firewall"

  printf 'hash-aaa' >"$splunkdb/firewall/db/db_100_90_0/rawdata/l2Hash_0_aaa.dat"
  printf 'hash-bbb' >"$splunkdb/firewall/db/db_200_190_1/rawdata/l2Hash_0_bbb.dat"
  printf 'hash-hot' >"$splunkdb/firewall/db/hot_v1_0/rawdata/l1Hashes_0_ccc.dat"
  printf 'hash-ddd' >"$splunkdb/other/db/db_1_0_0/rawdata/l2Hash_0_ddd.dat"

  # Pre-stamp firewall/db_100_90_0 with a valid mock token matching current hash.
  local hash_file="$splunkdb/firewall/db/db_100_90_0/rawdata/l2Hash_0_aaa.dat"
  local digest
  if command -v xxd >/dev/null 2>&1; then
    digest="$(xxd -p "$hash_file" | tr -d '\n')"
  else
    digest="$(od -An -v -tx1 "$hash_file" | tr -d ' \n')"
  fi
  printf 'MOCK-ZD:%s\n' "$digest" >"$kamusmdb/firewall/db_100_90_0.zd"
}

# --- tests ---

test_create_stamps_unsigned_skips_hot_and_stamped() {
  echo "TEST: create stamps only unstamped l2 buckets"
  local base out
  base="$(mktemp -d)"
  build_fixtures "$base"

  run_cli create --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb"
  assert_eq "exit 0" "0" "$RUN_RC"
  assert_file "stamped db_200_190_1" "$base/kamusmdb/firewall/db_200_190_1.zd"
  assert_file "stamped other db_1_0_0" "$base/kamusmdb/other/db_1_0_0.zd"
  assert_no_file "did not stamp hot bucket" "$base/kamusmdb/firewall/hot_v1_0.zd"
  assert_contains "skipped already stamped" "$RUN_OUT" "skipped:"
  assert_file "ledger exists" "$base/kamusmdb/ledger.csv"
  assert_contains "stamped count" "$RUN_OUT" "stamped: 2"

  rm -rf "$base"
}

test_create_dry_run() {
  echo "TEST: create --dry-run lists candidates, writes nothing"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"

  run_cli create --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb" --dry-run
  assert_eq "exit 0" "0" "$RUN_RC"
  assert_contains "lists db_200_190_1" "$RUN_OUT" "firewall/db_200_190_1"
  assert_contains "lists other" "$RUN_OUT" "other/db_1_0_0"
  assert_no_file "no new firewall token" "$base/kamusmdb/firewall/db_200_190_1.zd"
  assert_no_file "no other token" "$base/kamusmdb/other/db_1_0_0.zd"
  assert_no_file "no ledger" "$base/kamusmdb/ledger.csv"
  assert_contains "dry-run message" "$RUN_OUT" "Dry-run"

  rm -rf "$base"
}

test_create_index_filter() {
  echo "TEST: create --index firewall does not touch other"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"

  run_cli create --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb" --index firewall
  assert_eq "exit 0" "0" "$RUN_RC"
  assert_file "stamped firewall bucket" "$base/kamusmdb/firewall/db_200_190_1.zd"
  assert_no_file "did not stamp other" "$base/kamusmdb/other/db_1_0_0.zd"

  rm -rf "$base"
}

test_verify_reports_unstamped_and_passed() {
  echo "TEST: verify reports unstamped + passed for verify-ok"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"
  # Stamp remaining so only... actually leave db_200 and other unstamped
  run_cli verify --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb"
  assert_eq "exit 0 (no verify_failed)" "0" "$RUN_RC"
  assert_contains "verify_ok for pre-stamped" "$RUN_OUT" "verify_ok:     1"
  assert_contains "unstamped listed" "$RUN_OUT" "unstamped:"
  assert_contains "unstamped db_200" "$RUN_OUT" "firewall/db_200_190_1"
  assert_contains "passed with unstamped" "$RUN_OUT" "passed (with unstamped buckets)"

  rm -rf "$base"
}

test_verify_fails_on_bad_token() {
  echo "TEST: verify fails when mock marks a token bad"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"
  echo 'MOCK-ZD-BAD' >"$base/kamusmdb/firewall/db_100_90_0.zd"

  run_cli verify --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb" --index firewall
  assert_eq "exit non-zero" "1" "$RUN_RC"
  assert_contains "verify_failed" "$RUN_OUT" "verify_failed:"
  assert_contains "failed bucket" "$RUN_OUT" "firewall/db_100_90_0"

  rm -rf "$base"
}

test_orphan_zd_does_not_fail() {
  echo "TEST: orphan .zd does not fail verify"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"
  mkdir -p "$base/kamusmdb/firewall"
  echo 'orphan' >"$base/kamusmdb/firewall/db_orphan_gone.zd"

  # Stamp all so no unstamped noise for firewall+other — stamp everything first
  run_cli create --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb"
  run_cli verify --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb"
  assert_eq "exit 0" "0" "$RUN_RC"
  assert_contains "orphan listed" "$RUN_OUT" "orphan_tokens"
  assert_contains "orphan key" "$RUN_OUT" "firewall/db_orphan_gone"
  assert_contains "passed" "$RUN_OUT" "passed"

  rm -rf "$base"
}

test_strict_coverage_fails_on_unstamped() {
  echo "TEST: --strict-coverage fails when unstamped remain"
  local base
  base="$(mktemp -d)"
  build_fixtures "$base"

  run_cli verify --splunkdb "$base/splunkdb" --kamusmdb "$base/kamusmdb" --strict-coverage
  assert_eq "exit non-zero" "1" "$RUN_RC"
  assert_contains "strict message" "$RUN_OUT" "strict-coverage"

  rm -rf "$base"
}

main() {
  [[ -x "$CLI" ]] || chmod +x "$CLI"
  mkdir -p "$SCRIPT_DIR/output"
  local log_file="$SCRIPT_DIR/output/last_run.log"

  # Same-shell group (not a pipe) so PASS/FAIL stay visible; copy to gitignored log.
  {
    test_create_stamps_unsigned_skips_hot_and_stamped
    test_create_dry_run
    test_create_index_filter
    test_verify_reports_unstamped_and_passed
    test_verify_fails_on_bad_token
    test_orphan_zd_does_not_fail
    test_strict_coverage_fails_on_unstamped

    echo ""
    echo "Results: $PASS passed, $FAIL failed"
    echo "Log: $log_file"
  } >"$log_file" 2>&1

  cat "$log_file"
  [[ "$FAIL" -eq 0 ]]
}

main "$@"
