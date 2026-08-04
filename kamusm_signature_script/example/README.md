# KamuSM bucket signing — automation (clustered indexers)

Schedules `kamusm_timestamp.sh` so new warm/cold buckets get KamuSM (Zamane)
timestamps automatically, with periodic verify. Intended to run as the
**splunk** user on each indexer peer.

## Cluster model

- Run the signer on **every indexer** that holds local buckets.
- Keep `KAMUSMDB` **local to that host** (independent token stores; no shared
  filesystem required).
- At replication factor N, each peer stamps its own copy → up to **N stamps**
  per logical bucket (by design for peer-local stores).

Illustrative layout (adjust to your site):

| Path | Role |
|------|------|
| `/opt/kamusm/script/` | `kamusm_timestamp.sh`, Zamane jar, `kamusm_run.sh`, `kamusm.env` |
| `/opt/kamusm/db` | Local `.zd` tokens + `ledger.csv` |
| `/opt/kamusm/var/log` | Create/verify logs |
| `/opt/kamusm/var/run` | Per-mode flock files |
| `/opt/splunk/var/lib/splunk` | Splunk DB root (`SPLUNKDB`) — read-only for the signer |

Files in this bundle:

| File | Purpose |
|------|---------|
| `kamusm_run.sh` | Wrapper: sources config, per-mode `flock`, loops indexes, logs, propagates exit code. |
| `kamusm.env.example` | Config + credentials template. Copy to `kamusm.env`, chmod 0600. |
| `kamusm.cron` | Example `/etc/cron.d/kamusm`: hourly `create`, weekly `verify`. |

## Install

Deploy the same files on each indexer peer:

```bash
# wrapper + signer alongside the vendor jar
sudo install -o splunk -g splunk -m 0755 kamusm_run.sh /opt/kamusm/script/kamusm_run.sh
# also install kamusm_timestamp.sh, lib/, and the Zamane jar under /opt/kamusm/script/

# config from the example; then edit password + INDEXES
sudo install -o splunk -g splunk -m 0600 kamusm.env.example /opt/kamusm/script/kamusm.env
sudoedit /opt/kamusm/script/kamusm.env

# cron (runs as splunk); log/ and run/ dirs are created by the wrapper on first run
sudo install -o root -g root -m 0644 kamusm.cron /etc/cron.d/kamusm
```

Confirm cron can find Java (`which java`). If needed, set `EXTRA_PATH` in
`kamusm.env`.

## Splunk DB layout

The signer expects `db`, `colddb`, and `thaweddb` as siblings under each index,
e.g. `$SPLUNKDB/<index>/db/...` and `$SPLUNKDB/<index>/colddb/...`.

If `indexes.conf` splits hot/warm and cold onto **different roots**, a single
`SPLUNKDB` will miss one side — run the signer once per root (separate cron
lines / env files) or point `SPLUNKDB` at a tree that contains both.

## Dry run before going live

```bash
sudo -u splunk KAMUSM_ENV_FILE=/opt/kamusm/script/kamusm.env \
     /opt/kamusm/script/kamusm_run.sh create --dry-run
```

Lists buckets that would be stamped without calling KamuSM — useful to size the
first run and estimate credit usage (remember RF=N ⇒ up to N× stamps).

## How it lines up with Splunk

Splunk writes `l2Hash_*.dat` into a bucket's `rawdata/` when it rolls
**hot → warm** under `enableDataIntegrityControl = true`. The signer stamps each
l2Hash bucket that has no `.zd` yet and ignores hot buckets (they only have
`l1Hashes`). It is idempotent: re-runs only re-scan.

**Sign faster than buckets freeze.** A bucket is stampable only between rolling
to warm and hitting `frozenTimePeriodInSecs`. Keep the `create` interval well
under the shortest retention of any signed index — hourly for normal retention,
`*/15` for fast-rolling indexes. Freeze/archive tooling that only relocates
buckets (with l2Hash when present) does not stamp; tokens must exist beforehand.

The signer never writes under `$SPLUNKDB`; tokens land only under `$KAMUSMDB`.

## Operations

- **Logs:** `/opt/kamusm/var/log/{create,verify}-YYYYMMDD.log` plus a structured
  `kamusm_summary.log` line per run — both must be writable by `splunk`.
- **Locks:** `/opt/kamusm/var/run/kamusm-{create,verify}.lock` prevent overlapping
  runs on the same host.
- **Credentials:** live only in `kamusm.env` (0600). The Zamane jar still puts
  the password on its own command line briefly while running (upstream
  limitation).
- **Production TSA:** set `KAMUSM_TSA_URL=http://zd.kamusm.gov.tr` in `kamusm.env`
  (the tool otherwise defaults to the test server).
- **Back up `/opt/kamusm/db`** on each indexer — `.zd` tokens + `ledger.csv` are
  your tamper-evidence proof and should survive independently of Splunk DB.
- **SmartStore:** if any signed index uses S2, evicted buckets aren't local and
  can't be stamped; sign on a short interval before eviction or exclude them.

## Monitoring (optional)

Point a Splunk `inputs.conf` monitor at `/opt/kamusm/var/log/` and alert on
`mode=verify rc!=0` (tamper or coverage failure) and non-zero `create` runs;
ingest `/opt/kamusm/db/ledger.csv` for a searchable stamp audit trail.
