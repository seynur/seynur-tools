#!/usr/bin/env bash
#
# kamusm_timestamp.sh
#
# Locates the l2Hash (or l1Hashes, if the bucket hasn't rolled hot->warm yet) file
# that Splunk's Data Integrity Control feature produces for a bucket, and time-stamps
# it via TUBITAK KamuSM's official "Zamane" console client, then records an audit
# trail (ledger).
#
# WHY THE OFFICIAL JAR AND NOT RAW OPENSSL/CURL:
# KamuSM's TSA does not accept plain RFC3161 requests. Packet capture (redirecting
# the jar at a local loopback listener) confirmed it requires a proprietary
# "identity" HTTP header carrying an ASN.1 blob (customer no in cleartext as an
# INTEGER, followed by an encrypted credential payload) that only the official
# client can produce. Any request without it is TCP-reset by the server before any
# HTTP response is sent - confirmed with curl, custom User-Agents, and raw sockets.
# The official jar is therefore the only reliable integration path for now.
#
# Usage:
#   ./kamusm_timestamp.sh <BUCKET_PATH>
#   ./kamusm_timestamp.sh <HASH_FILE_PATH> [BUCKET_ID]
#
# Examples:
#   ./kamusm_timestamp.sh /opt/splunk/var/lib/splunk/kamusm/db/db_1784289623_1784289517_0
#   ./kamusm_timestamp.sh /opt/splunk/var/lib/splunk/kamusm/db/db_.../rawdata/l2Hash_0_XXXX.dat
#
# Requires:
#   - Java 1.8+ on PATH
#   - The Zamane console jar (KAMUSM_JAR_PATH, defaults to a jar next to this script)
#   - KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD environment variables
#
# SECURITY NOTE: the jar only accepts the password as a command-line argument, which
# is visible to other local users via `ps` for the (short) duration of the call. Run
# this only on hosts where that is an acceptable risk, or under a locked-down account.
#
set -euo pipefail

### --- CONFIG --- ###
TSA_URL="http://tzd.kamusm.gov.tr"      # Test server. Production: http://zd.kamusm.gov.tr
TSA_PORT="80"
HASH_ALG="sha-256"                       # Digest algorithm the jar uses to hash the input file

# KamuSM customer credentials - do not hardcode, read from environment:
#   export KAMUSM_CUSTOMER_NO=9207
#   export KAMUSM_CUSTOMER_PASSWORD='...'
CUSTOMER_NO="${KAMUSM_CUSTOMER_NO:-}"
CUSTOMER_PASSWORD="${KAMUSM_CUSTOMER_PASSWORD:-}"

# Zamane console jar: https://kamusm.bilgem.tubitak.gov.tr/urunler/zaman_damgasi/ucretsiz_zaman_damgasi_istemci_yazilimi.jsp
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR_PATH="${KAMUSM_JAR_PATH:-$SCRIPT_DIR/tss-client-console-3.1.33.jar}"

OUT_DIR="${KAMUSM_OUT_DIR:-$HOME/kamusm_timestamps}"   # Where timestamp tokens end up
LEDGER="${OUT_DIR}/ledger.csv"                          # Audit trail
### ---------------- ###

# --- Preflight: fail early with a clear message instead of a confusing mid-script error ---
missing=()
for bin in java find basename dirname; do
  command -v "$bin" >/dev/null 2>&1 || missing+=("$bin")
done
if [ ${#missing[@]} -gt 0 ]; then
  echo "ERROR: missing required tool(s): ${missing[*]}" >&2
  exit 10
fi
if [ ! -f "$JAR_PATH" ]; then
  echo "ERROR: Zamane console jar not found at: $JAR_PATH" >&2
  echo "       Download it or set KAMUSM_JAR_PATH to its location:" >&2
  echo "       https://kamusm.bilgem.tubitak.gov.tr/urunler/zaman_damgasi/ucretsiz_zaman_damgasi_istemci_yazilimi.jsp" >&2
  exit 11
fi
if [ -z "$CUSTOMER_NO" ] || [ -z "$CUSTOMER_PASSWORD" ]; then
  echo "ERROR: KAMUSM_CUSTOMER_NO / KAMUSM_CUSTOMER_PASSWORD are not set." >&2
  echo "       export KAMUSM_CUSTOMER_NO=9207" >&2
  echo "       export KAMUSM_CUSTOMER_PASSWORD='...'" >&2
  exit 12
fi

hex_encode() {
  if command -v xxd >/dev/null 2>&1; then
    xxd -p "$1" | tr -d '\n'
  else
    od -An -v -tx1 "$1" | tr -d ' \n'
  fi
}

usage() {
  echo "Usage:" >&2
  echo "  $0 [--force] <BUCKET_PATH>" >&2
  echo "  $0 [--force] <HASH_FILE_PATH> [BUCKET_ID]" >&2
  echo "" >&2
  echo "  --force  re-timestamp a bucket that already has a ledger entry" >&2
  exit 1
}

FORCE=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
set -- "${ARGS[@]}"

[ $# -ge 1 ] || usage
INPUT="$1"
BUCKET_ID="${2:-}"
HASH_KIND="file"

if [ -d "$INPUT" ]; then
  # --- Input is a bucket directory: locate l2Hash / l1Hashes ---
  BUCKET_DIR="$INPUT"
  BUCKET_ID="${BUCKET_ID:-$(basename "$BUCKET_DIR")}"

  HASH_FILE=$(find "$BUCKET_DIR/rawdata" -maxdepth 1 -iname 'l2Hash_*.dat' 2>/dev/null | head -1)
  HASH_KIND="l2Hash"
  if [ -z "$HASH_FILE" ]; then
    # Bucket hasn't rolled from hot to warm yet, so l2Hash doesn't exist - fall back to l1Hashes
    HASH_FILE=$(find "$BUCKET_DIR/rawdata" -maxdepth 1 -iname 'l1Hashes_*.dat' 2>/dev/null | head -1)
    HASH_KIND="l1Hashes"
  fi

  if [ -z "$HASH_FILE" ]; then
    echo "ERROR: no l2Hash_*.dat / l1Hashes_*.dat found under $BUCKET_DIR/rawdata." >&2
    echo "       The index needs enableDataIntegrityControl=true." >&2
    echo "       If missing: \$SPLUNK_HOME/bin/splunk generate-hash-files -bucketPath \"$BUCKET_DIR\" -verbose" >&2
    exit 2
  fi
  echo "Bucket                : $BUCKET_DIR"
  echo "Hash file ($HASH_KIND) : $HASH_FILE"
elif [ -f "$INPUT" ]; then
  # --- Input is a l2Hash/l1Hashes .dat file directly ---
  HASH_FILE="$INPUT"
  case "$(basename "$HASH_FILE")" in
    l2Hash_*)    HASH_KIND="l2Hash" ;;
    l1Hashes_*)  HASH_KIND="l1Hashes" ;;
    *)           HASH_KIND="file" ;;
  esac
  # rawdata/l2Hash_...dat -> the bucket directory is one level up
  BUCKET_ID="${BUCKET_ID:-$(basename "$(dirname "$(dirname "$HASH_FILE")")")}"
  echo "Hash file ($HASH_KIND) : $HASH_FILE"
else
  echo "ERROR: '$INPUT' is neither a bucket directory nor an existing file." >&2
  echo "       The jar hashes an actual file - write the hash bytes to a file first" >&2
  echo "       if you only have a hex string." >&2
  exit 2
fi

HASH_HEX=$(hex_encode "$HASH_FILE")
echo "Hash (hex)            : $HASH_HEX"

mkdir -p "$OUT_DIR"

# --- Idempotency guard: a bucket should only be timestamped once ---
if [ -f "$LEDGER" ]; then
  PRIOR=$(awk -F',' -v b="$BUCKET_ID" 'NR>1 && $2==b {print}' "$LEDGER")
  if [ -n "$PRIOR" ] && [ "$FORCE" -ne 1 ]; then
    echo "ERROR: bucket '$BUCKET_ID' already has a timestamp in the ledger:" >&2
    echo "$PRIOR" >&2
    PRIOR_HASH=$(echo "$PRIOR" | tail -1 | awk -F',' '{print $4}')
    if [ "$PRIOR_HASH" != "$HASH_HEX" ]; then
      echo "WARNING: the current hash ($HASH_HEX) differs from the recorded one" >&2
      echo "         ($PRIOR_HASH) - the bucket's data may have changed since it was" >&2
      echo "         last stamped. Investigate before re-stamping." >&2
    fi
    echo "Use --force to re-timestamp anyway." >&2
    exit 5
  fi
  if [ -n "$PRIOR" ] && [ "$FORCE" -eq 1 ]; then
    echo "NOTE: --force set, re-timestamping bucket '$BUCKET_ID' despite existing ledger entry." >&2
  fi
fi
TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
SAFE_ID="${BUCKET_ID//\//_}"
DEST_TOKEN="${OUT_DIR}/${SAFE_ID}_${TS_UTC}.zd"

echo "[1/2] Requesting + verifying timestamp via Zamane (customer $CUSTOMER_NO)..."
JAR_OUTPUT_FILE="${HASH_FILE}.zd"
rm -f "$JAR_OUTPUT_FILE"

# -ZC both requests the timestamp and verifies the TSA's certificate signature in one step.
if ! java -jar "$JAR_PATH" -ZC "$HASH_FILE" "$TSA_URL" "$TSA_PORT" "$CUSTOMER_NO" "$CUSTOMER_PASSWORD" "$HASH_ALG"; then
  echo "ERROR: Zamane client reported a failure - see the log above." >&2
  exit 3
fi

if [ ! -f "$JAR_OUTPUT_FILE" ]; then
  echo "ERROR: expected token file not found: $JAR_OUTPUT_FILE" >&2
  exit 4
fi

echo "[2/2] Moving the token out of the bucket into $OUT_DIR..."
mv "$JAR_OUTPUT_FILE" "$DEST_TOKEN"

# Append to the audit ledger
if [ ! -f "$LEDGER" ]; then
  echo "timestamp_utc,bucket_id,hash_kind,hash,hash_file,token_file" > "$LEDGER"
fi
echo "${TS_UTC},${BUCKET_ID},${HASH_KIND},${HASH_HEX},${HASH_FILE},${DEST_TOKEN}" >> "$LEDGER"

echo ""
echo "Done."
echo "  Token : $DEST_TOKEN"
echo "  Log   : $LEDGER"
echo ""
echo "To re-verify later: java -jar \"$JAR_PATH\" -C \"$HASH_FILE\" \"$DEST_TOKEN\""
