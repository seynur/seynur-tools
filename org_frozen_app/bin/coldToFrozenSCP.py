#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# coldToFrozenSCP.py — archive frozen payload (rawdata/journal* + optional
# rawdata/l2hash) to a remote host over scp before Splunk removes the bucket.
# Exit 0 only after stage + verify + promote.
#
# indexes.conf (cluster indexes bundle), per index or [default]:
#   coldToFrozenScript = "$SPLUNK_HOME/bin/python3" \
#     "$SPLUNK_HOME/etc/apps/org_frozen_app/bin/coldToFrozenSCP.py"
#
# REMOTE_HOST is a stable logical name; differentiate prod/DR via /etc/hosts
# on each indexer so the same app and indexes.conf work everywhere.

import os
import shutil
import sys

import frozen_common as common

# ------------------------- configuration (edit me) -------------------------
REMOTE_USER = "splunkarch"
REMOTE_HOST = "archive.internal.seynur.com"    # resolve via /etc/hosts per env
REMOTE_BASE = "/srv/splunk_frozen"             # .../<index>/<bucket>/rawdata/...
SSH_KEY = "/opt/splunk/.ssh/id_frozen"
SSH_PORT = "22"
SCP_TIMEOUT = 3600
# ---------------------------------------------------------------------------

logger = common.setup_logger("scp")


def ssh_base_opts():
    """Shared SSH/SCP options (DRY). Caller adds -p/-P for port."""
    return [
        "-i", SSH_KEY,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=30",
    ]


def ssh_cmd(*remote_args):
    return (
        ["ssh", "-p", SSH_PORT]
        + ssh_base_opts()
        + ["%s@%s" % (REMOTE_USER, REMOTE_HOST)]
        + list(remote_args)
    )


def scp_cmd(local_path, remote_spec):
    return (
        ["scp", "-r", "-p", "-B", "-P", SSH_PORT]
        + ssh_base_opts()
        + [local_path, remote_spec]
    )


def remote_file_count(remote_path):
    """Count files under remote_path via argv-only find (no shell string)."""
    rc, out, err = common.run(
        ssh_cmd("find", remote_path, "-type", "f"), 120)
    if rc != 0:
        return -1, common.decode(err)
    lines = [ln for ln in common.decode(out).splitlines() if ln.strip()]
    return len(lines), ""


def main():
    try:
        bucket, index, bucket_name = common.parse_bucket_arg(sys.argv)
        artifacts = common.collect_frozen_artifacts(bucket)
    except ValueError as exc:
        common.die(logger, "<none>" if len(sys.argv) < 2 else sys.argv[1],
                   error=str(exc))

    dest = "%s@%s" % (REMOTE_USER, REMOTE_HOST)
    remote_dir = "%s/%s" % (REMOTE_BASE, index)
    stage_name = "%s.partial.%d" % (bucket_name, os.getpid())
    remote_stage = "%s/%s" % (remote_dir, stage_name)
    remote_final = "%s/%s" % (remote_dir, bucket_name)
    expected = len(artifacts)

    logger.info(common.kv_fields(
        status="start", bucket=bucket, index=index,
        dest="%s:%s" % (dest, remote_final), files=expected))

    staging = None
    try:
        staging = common.build_frozen_staging_dir(artifacts)

        rc, _out, err = common.run(ssh_cmd("mkdir", "-p", remote_dir), 60)
        if rc != 0:
            common.die(logger, bucket, error="remote mkdir failed",
                       rc=rc, detail=common.decode(err))

        common.run(ssh_cmd("rm", "-rf", remote_stage), 120)

        # scp -r staging host:remote_stage → remote_stage/rawdata/...
        rc, _out, err = common.run(
            scp_cmd(staging, "%s:%s" % (dest, remote_stage)), SCP_TIMEOUT)
        if rc != 0:
            common.run(ssh_cmd("rm", "-rf", remote_stage), 120)
            common.die(logger, bucket, error="scp failed",
                       rc=rc, detail=common.decode(err))

        remote_count, find_err = remote_file_count(remote_stage)
        if remote_count != expected:
            common.run(ssh_cmd("rm", "-rf", remote_stage), 120)
            common.die(
                logger, bucket,
                error="integrity check failed",
                local_files=expected, remote_files=remote_count,
                detail=find_err)

        rc, _out, err = common.run(ssh_cmd("rm", "-rf", remote_final), 120)
        if rc != 0:
            common.die(logger, bucket,
                       error="remote cleanup of prior archive failed",
                       rc=rc, detail=common.decode(err))

        rc, _out, err = common.run(
            ssh_cmd("mv", remote_stage, remote_final), 120)
        if rc != 0:
            common.die(logger, bucket, error="remote promote failed",
                       rc=rc, detail=common.decode(err))
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    logger.info(common.kv_fields(
        status="success", bucket=bucket, index=index,
        dest="%s:%s" % (dest, remote_final), files=expected))
    sys.exit(0)


if __name__ == "__main__":
    main()
