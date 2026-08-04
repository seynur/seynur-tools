# KamuSM Splunk bucket timestamping

Batch-create and verify **TÜBİTAK KamuSM (Zamane)** timestamps for Splunk warm/cold buckets that have Data Integrity Control enabled (`l2Hash_*.dat`).

## Scripts

| File | Purpose |
|------|---------|
| [`kamusm_timestamp.sh`](kamusm_timestamp.sh) | Batch `create` / `verify` over `$SPLUNKDB` |
| [`lib/kamusm_common.sh`](lib/kamusm_common.sh) | Shared helpers + jar/mock backends |
| [`example/`](example/) | Cron wrapper, env example, and clustered-indexer install notes |
| [`tests/run_tests.sh`](tests/run_tests.sh) | Mock-backend tests (no network / no jar) |

## Contracts

- Tokens are written only under `$KAMUSMDB` as `$KAMUSMDB/<index>/<bucket_id>.zd` (plus `ledger.csv`).
- `create` / `verify` never write under `$SPLUNKDB` (bucket dirs stay read-only). The jar backend stamps a copy in a private scratch dir, then moves the `.zd` into `$KAMUSMDB`.

## Prerequisites

- Bash (macOS 3.2+, Linux Bash 4+)
- Java 1.8+ on `PATH` (only for live jar backend)
- [Zamane console client jar](https://kamusm.bilgem.tubitak.gov.tr/urunler/zaman_damgasi/ucretsiz_zaman_damgasi_istemci_yazilimi.jsp) (`tss-client-console-*.jar`)
- KamuSM customer number and password
- Splunk indexes with `enableDataIntegrityControl=true` (so warm/cold buckets have `rawdata/l2Hash_*.dat`)

## Quick start

```bash
cd kamusm_signature_script

# Credentials (required for live stamping)
export KAMUSM_CUSTOMER_NO=9207
export KAMUSM_CUSTOMER_PASSWORD='...'

# Optional: jar location (default: ./tss-client-console-3.1.33.jar)
export KAMUSM_JAR_PATH=/path/to/tss-client-console-3.1.33.jar

# Optional: production TSA (default is test server tzd.kamusm.gov.tr)
# export KAMUSM_TSA_URL=http://zd.kamusm.gov.tr
# export KAMUSM_TSA_PORT=80
```

### Create timestamps (stamp unstamped l2Hash buckets)

```bash
./kamusm_timestamp.sh create \
  --splunkdb /opt/splunk/var/lib/splunk \
  --kamusmdb /opt/kamusm/db

# One index only
./kamusm_timestamp.sh create \
  --splunkdb /opt/splunk/var/lib/splunk \
  --kamusmdb /opt/kamusm/db \
  --index firewall

# Preview without calling KamuSM
./kamusm_timestamp.sh create \
  --splunkdb /opt/splunk/var/lib/splunk \
  --kamusmdb /opt/kamusm/db \
  --dry-run

# Re-stamp buckets that already have a .zd
./kamusm_timestamp.sh create ... --force
```

### Verify timestamps

```bash
./kamusm_timestamp.sh verify \
  --splunkdb /opt/splunk/var/lib/splunk \
  --kamusmdb /opt/kamusm/db

./kamusm_timestamp.sh verify \
  --splunkdb /opt/splunk/var/lib/splunk \
  --kamusmdb /opt/kamusm/db \
  --index firewall

# Also fail if any l2Hash bucket lacks a .zd
./kamusm_timestamp.sh verify ... --strict-coverage
```

## Where tokens are stored

```text
$KAMUSMDB/<index>/<bucket_id>.zd
$KAMUSMDB/ledger.csv          # audit trail only
```

Example: `/opt/kamusm/db/firewall/db_1784289623_1784289517_0.zd`

The script stamps only buckets that already have `l2Hash` (warm/cold/thawed under `db`, `colddb`, `thaweddb`). Hot buckets with only `l1Hashes` are ignored.

## Automation (clustered indexers)

See [`example/`](example/) for a scheduler-friendly wrapper (`kamusm_run.sh`), cron snippet, and env template. Deploy on each indexer peer with a **local** `$KAMUSMDB`.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KAMUSM_CUSTOMER_NO` | (required for jar) | KamuSM customer number |
| `KAMUSM_CUSTOMER_PASSWORD` | (required for jar) | KamuSM password |
| `KAMUSM_JAR_PATH` | `./tss-client-console-3.1.33.jar` | Path to Zamane console jar |
| `KAMUSM_BACKEND` | `jar` | `jar` (live TSA) or `mock` (tests) |
| `KAMUSM_TSA_URL` | `http://tzd.kamusm.gov.tr` | Test TSA; prod: `http://zd.kamusm.gov.tr` |
| `KAMUSM_TSA_PORT` | `80` | TSA port |
| `KAMUSM_HASH_ALG` | `sha-256` | Digest algorithm passed to the jar |

## Security note

The Zamane jar accepts the password as a command-line argument, which can appear in `ps` for a short time. Run under a locked-down account on hosts where that risk is acceptable.

## Tests (no network / no jar)

```bash
./tests/run_tests.sh
```

This sets `KAMUSM_BACKEND=mock` and builds temporary fixture trees. Test output under `tests/output/` is gitignored.

## Help

```bash
./kamusm_timestamp.sh --help
```
