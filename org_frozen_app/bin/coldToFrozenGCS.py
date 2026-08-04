#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# coldToFrozenGCS.py — archive frozen payload (rawdata/journal* + optional
# rawdata/l2hash) to GCS (stage → verify → promote).
#
# Production uses gsutil. EMULATOR_HOST enables fake-gcs-server HTTP uploads
# (direct-to-final; staging applies to the gsutil path only).

import os
import shutil
import sys

import frozen_common as common

# ------------------------- configuration (edit me) -------------------------
# e.g. "gs://my-bucket/frozen_buckets"  (no trailing slash)
GCS_BUCKET = "gs://<GCS-PATH>"
# Set for local fake-gcs-server; leave empty for production gsutil
EMULATOR_HOST = ""
# ---------------------------------------------------------------------------

logger = common.setup_logger("gcs")


def _gs_path(*parts):
    base = GCS_BUCKET.rstrip("/")
    bits = [p.strip("/") for p in parts if p and str(p).strip("/")]
    return "%s/%s" % (base, "/".join(bits)) if bits else base


def _gsutil(*args, timeout=3600):
    return common.run(["gsutil", "-m"] + list(args), timeout)


def remote_file_count(gs_uri):
    """Count objects under a gs:// prefix via gsutil ls -r."""
    rc, out, err = _gsutil("ls", "-r", gs_uri.rstrip("/") + "/**", timeout=300)
    if rc != 0:
        text = common.decode(err) or common.decode(out)
        if "matched no objects" in text:
            return 0, ""
        return -1, text
    lines = [
        ln for ln in common.decode(out).splitlines()
        if ln.startswith("gs://") and not ln.endswith(":") and not ln.endswith("/")
    ]
    return len(lines), ""


def upload_via_emulator(staging_dir, dest_uri):
    """Upload staging tree to fake-gcs-server. Returns files uploaded."""
    import urllib.parse
    import urllib.request

    without = dest_uri[len("gs://"):]
    bucket_name, _, blob_root = without.partition("/")
    uploaded = 0
    for root, _dirs, files in os.walk(staging_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, staging_dir).replace(os.sep, "/")
            blob_path = "%s/%s" % (blob_root, rel) if blob_root else rel
            encoded = urllib.parse.quote(blob_path, safe="")
            url = (
                "%s/upload/storage/v1/b/%s/o?uploadType=media&name=%s"
                % (EMULATOR_HOST.rstrip("/"), bucket_name, encoded)
            )
            with open(full, "rb") as handle:
                data = handle.read()
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/octet-stream")
            urllib.request.urlopen(req)
            uploaded += 1
    return uploaded


def archive_with_gsutil(staging_dir, bucket, stage_uri, final_uri, expected):
    _gsutil("rm", "-r", stage_uri, timeout=300)

    rc, _out, err = _gsutil("rsync", "-r", staging_dir, stage_uri, timeout=3600)
    if rc != 0:
        _gsutil("rm", "-r", stage_uri, timeout=300)
        common.die(logger, bucket, error="gsutil rsync failed",
                   rc=rc, detail=common.decode(err))

    remote_count, find_err = remote_file_count(stage_uri)
    if remote_count != expected:
        _gsutil("rm", "-r", stage_uri, timeout=300)
        common.die(
            logger, bucket,
            error="integrity check failed",
            local_files=expected, remote_files=remote_count,
            detail=find_err)

    _gsutil("rm", "-r", final_uri, timeout=300)
    rc, _out, err = _gsutil("rsync", "-r", stage_uri, final_uri, timeout=3600)
    if rc != 0:
        common.die(logger, bucket, error="gcs promote failed",
                   rc=rc, detail=common.decode(err))
    _gsutil("rm", "-r", stage_uri, timeout=300)


def main():
    try:
        bucket, index, bucket_name = common.parse_bucket_arg(sys.argv)
        artifacts = common.collect_frozen_artifacts(bucket)
    except ValueError as exc:
        common.die(logger, "<none>" if len(sys.argv) < 2 else sys.argv[1],
                   error=str(exc))

    stage_uri = _gs_path(index, "%s.partial.%d" % (bucket_name, os.getpid()))
    final_uri = _gs_path(index, bucket_name)
    dest = final_uri
    expected = len(artifacts)

    logger.info(common.kv_fields(
        status="start", bucket=bucket, index=index, dest=dest, files=expected))

    staging = None
    try:
        staging = common.build_frozen_staging_dir(artifacts)
        if EMULATOR_HOST:
            uploaded = upload_via_emulator(staging, final_uri)
            if uploaded != expected:
                common.die(
                    logger, bucket,
                    error="integrity check failed",
                    local_files=expected, remote_files=uploaded)
        else:
            archive_with_gsutil(staging, bucket, stage_uri, final_uri, expected)
    except SystemExit:
        raise
    except Exception as exc:
        if not EMULATOR_HOST:
            _gsutil("rm", "-r", stage_uri, timeout=300)
        common.die(logger, bucket, error="gcs archive failed", detail=str(exc))
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    logger.info(common.kv_fields(
        status="success", bucket=bucket, index=index, dest=dest, files=expected))
    sys.exit(0)


if __name__ == "__main__":
    main()
