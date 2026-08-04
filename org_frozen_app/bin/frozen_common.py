#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared helpers for org_frozen_app coldToFrozen scripts.

Logging goes to $SPLUNK_HOME/var/log/splunk/frozen_app.log (KV lines) so the
default Splunk directory monitor picks it up into index=_internal.
"""

from __future__ import print_function

import glob
import logging
import logging.handlers
import os
import shutil
import subprocess
import sys
import tempfile

LOG_NAME = "frozen_app.log"
_DB_PARENTS = ("colddb", "db", "frozendb")


def setup_logger(component):
    """Return a logger that appends KV lines to frozen_app.log."""
    splunk_home = os.environ.get("SPLUNK_HOME", "/opt/splunk")
    log_path = os.path.join(splunk_home, "var", "log", "splunk", LOG_NAME)

    logger = logging.getLogger("frozen_app.%s" % component)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=25 * 1024 * 1024, backupCount=5)
        fmt = (
            "%(asctime)s level=%(levelname)s component=%(component)s "
            "host=%(hostname)s %(message)s"
        )
        handler.setFormatter(logging.Formatter(fmt))
        logging.Formatter.default_msec_format = "%s.%03d"

        class _ContextFilter(logging.Filter):
            def filter(self, record):
                record.hostname = os.uname()[1]
                record.component = component
                return True

        handler.addFilter(_ContextFilter())
        logger.addHandler(handler)
    return logger


def kv_fields(**fields):
    """Format kwargs as key=value pairs for KV log lines."""
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value)
        if any(c in text for c in (' ', '"', '=')):
            text = '"%s"' % text.replace('"', '\\"')
        parts.append("%s=%s" % (key, text))
    return " ".join(parts)


def die(logger, bucket, **fields):
    """Log status=failed and exit non-zero so Splunk keeps the local bucket."""
    logger.error(kv_fields(status="failed", bucket=bucket, **fields))
    sys.exit(1)


def decode(stream):
    """Decode subprocess stdout/stderr bytes to a stripped unicode string."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", "replace").strip()
    return str(stream).strip()


def run(cmd, timeout):
    """Run cmd; return (rc, stdout, stderr). Timeout yields rc=124."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return 124, out, err
    return proc.returncode, out, err


def local_file_count(path):
    """Count regular files under path (recursive)."""
    return sum(len(files) for _, _, files in os.walk(path))


def collect_frozen_artifacts(bucket_path):
    """
    Collect thawable frozen payload from a Splunk bucket.

    Returns list of (abs_src, relpath) where relpath is relative to the
    destination bucket root (e.g. rawdata/journal.zst).

    Requires exactly one regular file matching rawdata/journal*.
    Includes rawdata/l2hash when that file exists.
    Raises ValueError on missing rawdata, zero journals, or multiple journals.
    """
    bucket_path = os.path.abspath(bucket_path.rstrip(os.sep))
    rawdata = os.path.join(bucket_path, "rawdata")
    if not os.path.isdir(rawdata):
        raise ValueError("bucket has no rawdata directory: %s" % bucket_path)

    journals = sorted(
        p for p in glob.glob(os.path.join(rawdata, "journal*"))
        if os.path.isfile(p)
    )
    if len(journals) == 0:
        raise ValueError("no rawdata/journal* file found in %s" % bucket_path)
    if len(journals) > 1:
        names = ", ".join(os.path.basename(p) for p in journals)
        raise ValueError(
            "expected exactly one rawdata/journal* file, found %d: %s"
            % (len(journals), names)
        )

    artifacts = [(journals[0], os.path.join("rawdata", os.path.basename(journals[0])))]
    l2hash = os.path.join(rawdata, "l2hash")
    if os.path.isfile(l2hash):
        artifacts.append((l2hash, os.path.join("rawdata", "l2hash")))
    return artifacts


def build_frozen_staging_dir(artifacts):
    """
    Build a temp directory containing only frozen artifacts under rawdata/.

    Uses hardlinks when possible, otherwise copies. Caller must remove the
    returned directory (e.g. shutil.rmtree).
    """
    tmp = tempfile.mkdtemp(prefix="frozen_stage_")
    try:
        for abs_src, relpath in artifacts:
            dest = os.path.join(tmp, relpath.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                os.link(abs_src, dest)
            except OSError:
                shutil.copy2(abs_src, dest)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return tmp


def index_from_bucket_path(path):
    """
    Derive index name from a Splunk bucket path.

    Expects .../<index>/(colddb|db|frozendb)/<bucket>. Raises ValueError if
    the layout cannot be determined.
    """
    path = os.path.abspath(path.rstrip(os.sep))
    parent = os.path.basename(os.path.dirname(path))
    if parent in _DB_PARENTS:
        index = os.path.basename(os.path.dirname(os.path.dirname(path)))
        if index:
            return index
    raise ValueError(
        "cannot derive index from bucket path (expected .../<index>/"
        "colddb|db|frozendb/<bucket>): %s" % path
    )


def parse_bucket_arg(argv):
    """
    Validate sys.argv-style args for coldToFrozenScript.

    Returns (bucket_path, index_name, bucket_name).
    Raises ValueError on bad input (caller should die()).
    """
    if len(argv) < 2:
        raise ValueError("no bucket path argument was passed")
    bucket = os.path.abspath(argv[1].rstrip(os.sep))
    if not os.path.isdir(bucket):
        raise ValueError("bucket path is not a directory or does not exist")
    index = index_from_bucket_path(bucket)
    bucket_name = os.path.basename(bucket)
    return bucket, index, bucket_name
