# org_frozen_app

Splunk `coldToFrozenScript` backends that archive the **thawable frozen payload**
— exactly one `rawdata/journal*` plus optional `rawdata/l2hash` — to SCP, S3, or
GCS before Splunk deletes the local bucket. Shared helpers live in
`bin/frozen_common.py`. Activity is logged as KV lines to
`$SPLUNK_HOME/var/log/splunk/frozen_app.log` (picked up by Splunk’s default
`var/log/splunk` monitor into `index=_internal`).

The `org_` app prefix is intentional for customer rename (e.g. `acme_frozen_app`).
The log file name stays generic: `frozen_app.log`.

## Packaging (important)

When shipping this as a Splunk app, **exclude the `tests/` directory**. It is
for development only and must not be deployed to indexers.

Suggested package contents:

- `bin/` (scripts + `frozen_common.py`)
- `local/` (`app.conf`; not `indexes.conf.example` as live config)
- `metadata/`
- `README.md` (optional on target)

## Scripts

| Script | Destination |
|--------|-------------|
| `bin/coldToFrozenSCP.py` | Remote host over SSH/scp |
| `bin/coldToFrozenS3.py` | AWS S3 / S3-compatible (boto3) |
| `bin/coldToFrozenGCS.py` | Google Cloud Storage (gsutil) |

Edit the configuration block at the top of the script you enable.

## Destination layout

```text
{dest}/{index}/{bucket_name}/rawdata/journal.<ext>
{dest}/{index}/{bucket_name}/rawdata/l2hash    # only if present locally
```

This matches Splunk’s frozen / thawable shape (rawdata-centric), not a full
warm/cold bucket tree.

## Design decisions

- Conf ships under `local/` (internal/custom app convention).
- Payload is collected once in `frozen_common` (`collect_frozen_artifacts` +
  `build_frozen_staging_dir`); backends only transport, verify, and promote.
- Exactly one `rawdata/journal*` is required (fail if zero or multiple);
  `rawdata/l2hash` is included when data integrity is enabled.
- Flow is **stage → artifact-count verify → promote** so a failed copy does not
  replace a good prior archive.
- **Synchronous** archive to the real destination before exit 0: Splunk deletes
  the local bucket only after a successful exit, so returning early after a
  local spool alone would risk data loss.
- No `inputs.conf` / `props.conf`: rely on the default log monitor; KV fields
  extract from the raw event. Alert with `source=*frozen_app.log`.
- SCP `REMOTE_HOST` is a stable logical name; point prod vs DR archive IPs via
  `/etc/hosts` on each indexer so the same app and indexes bundle can be used.
- Destination path does **not** include peer hostname. On a cluster with RF>1,
  each peer may archive the same `{index}/{bucket_name}/`; `.partial.<pid>`
  avoids mid-flight collisions, and a later promote may overwrite another peer’s
  copy of the same bucket (usually equivalent data). Use per-peer archive roots
  if you need distinct copies.

## Future enhancement (not implemented)

Splunk docs suggest finishing `coldToFrozenScript` quickly on slow volumes by
copying to a fast local temp and moving to the final archive with a separate
process. A two-phase **async local spool** could be added later if archive
latency becomes a problem; it must not exit 0 until the durable archive is
confirmed (or an equally safe handoff exists).

## Logging and alerts

```
index=_internal source=*frozen_app.log
index=_internal source=*frozen_app.log status=failed
```

Example line:

```
2026-08-04 12:00:00.123 level=INFO component=scp status=start bucket="..." index=... dest=... files=...
```

## indexes.conf

`coldToFrozenScript` belongs in your **indexes** bundle, not this app. See
`local/indexes.conf.example`. On cluster peers prefer the `slave-apps` path
after a CM push; verify with `ls` on a peer.

## Failure contract

- Exit `0` → Splunk deletes the local bucket.
- Exit non-zero → Splunk keeps the bucket and retries on the next freeze cycle.

## Backend setup notes

### SCP

1. As `splunk`, create and trust an SSH key on the archive host.
2. Set `REMOTE_*` / `SSH_*` in `coldToFrozenSCP.py`.
3. Ensure `/etc/hosts` maps `REMOTE_HOST` to the correct archive IP per site.

### S3

- Install `boto3` for the Python used in `coldToFrozenScript`.
- Set `S3_BUCKET_NAME` / optional `S3_PREFIX`; use `LOCALSTACK_ENDPOINT` for local tests.
- Credentials via the usual AWS env / instance role / config.

### GCS

- `gsutil` on PATH and authenticated (user or service account).
- Set `GCS_BUCKET` (e.g. `gs://my-bucket/frozen`).
- `EMULATOR_HOST` for fake-gcs-server (direct upload to final prefix).

## Manual E2E checklist

1. As the `splunk` user, run the chosen script against a sample cold bucket path.
2. Confirm only `rawdata/journal*` (and `l2hash` if present) landed under
   `{index}/{bucket_name}/`; confirm `status=success` in `frozen_app.log`.
3. Force a failure (bad key / missing journal) and confirm exit ≠ 0,
   `status=failed` in the log.
4. Confirm `index=_internal source=*frozen_app.log` shows KV fields.

## Unit tests

```bash
cd org_frozen_app
python3 -m unittest tests.test_frozen_common -v
```

Do not include `tests/` in the Splunk app tarball.

## KamuSM note

Frozen archive includes `rawdata/journal*` and `rawdata/l2hash` when present.
KamuSM `.zd` tokens under `/opt/kamusm/db` are separate — back those up
alongside the frozen archive.
