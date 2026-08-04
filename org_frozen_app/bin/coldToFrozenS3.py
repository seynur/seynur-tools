#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# coldToFrozenS3.py — archive frozen payload (rawdata/journal* + optional
# rawdata/l2hash) to S3 (stage → verify → promote).
#
# Requires boto3 available to Splunk's Python (or system python3 used in
# coldToFrozenScript).

import os
import shutil
import sys

import frozen_common as common

# ------------------------- configuration (edit me) -------------------------
S3_BUCKET_NAME = "<S3-BUCKET-NAME>"
# Optional key prefix (no leading/trailing slash), e.g. "frozen"
S3_PREFIX = ""
# Set for LocalStack / custom endpoint; leave empty for real AWS
LOCALSTACK_ENDPOINT = ""
# ---------------------------------------------------------------------------

logger = common.setup_logger("s3")


def _s3_client():
    import boto3
    if LOCALSTACK_ENDPOINT:
        return boto3.client(
            "s3",
            endpoint_url=LOCALSTACK_ENDPOINT,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )
    return boto3.client("s3")


def _key(prefix_parts, *parts):
    bits = [p.strip("/") for p in prefix_parts + list(parts) if p and str(p).strip("/")]
    return "/".join(bits)


def _prefix_root():
    return [S3_PREFIX] if S3_PREFIX else []


def upload_staging_dir(client, local_dir, key_prefix):
    """Upload every file under local_dir to s3://bucket/key_prefix/..."""
    for root, _dirs, files in os.walk(local_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, local_dir).replace(os.sep, "/")
            client.upload_file(full, S3_BUCKET_NAME, "%s/%s" % (key_prefix, rel))


def count_objects(client, key_prefix):
    prefix = key_prefix.rstrip("/") + "/"
    count = 0
    token = None
    while True:
        kwargs = {"Bucket": S3_BUCKET_NAME, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        count += len(resp.get("Contents") or [])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return count


def list_keys(client, key_prefix):
    prefix = key_prefix.rstrip("/") + "/"
    keys = []
    token = None
    while True:
        kwargs = {"Bucket": S3_BUCKET_NAME, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            keys.append(obj["Key"])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def delete_prefix(client, key_prefix):
    keys = list_keys(client, key_prefix)
    for i in range(0, len(keys), 1000):
        chunk = keys[i:i + 1000]
        if not chunk:
            continue
        client.delete_objects(
            Bucket=S3_BUCKET_NAME,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
        )


def promote_prefix(client, stage_prefix, final_prefix):
    """Copy stage objects to final keys, then delete stage."""
    stage_prefix = stage_prefix.rstrip("/")
    final_prefix = final_prefix.rstrip("/")
    keys = list_keys(client, stage_prefix)
    for key in keys:
        rel = key[len(stage_prefix) + 1:]
        dest_key = "%s/%s" % (final_prefix, rel)
        client.copy_object(
            Bucket=S3_BUCKET_NAME,
            CopySource={"Bucket": S3_BUCKET_NAME, "Key": key},
            Key=dest_key,
        )
    delete_prefix(client, stage_prefix)


def main():
    try:
        bucket, index, bucket_name = common.parse_bucket_arg(sys.argv)
        artifacts = common.collect_frozen_artifacts(bucket)
    except ValueError as exc:
        common.die(logger, "<none>" if len(sys.argv) < 2 else sys.argv[1],
                   error=str(exc))

    root = _prefix_root()
    stage_prefix = _key(root, index, "%s.partial.%d" % (bucket_name, os.getpid()))
    final_prefix = _key(root, index, bucket_name)
    dest = "s3://%s/%s" % (S3_BUCKET_NAME, final_prefix)
    expected = len(artifacts)

    logger.info(common.kv_fields(
        status="start", bucket=bucket, index=index, dest=dest, files=expected))

    staging = None
    try:
        staging = common.build_frozen_staging_dir(artifacts)
        client = _s3_client()

        delete_prefix(client, stage_prefix)
        upload_staging_dir(client, staging, stage_prefix)

        remote_count = count_objects(client, stage_prefix)
        if remote_count != expected:
            delete_prefix(client, stage_prefix)
            common.die(
                logger, bucket,
                error="integrity check failed",
                local_files=expected, remote_files=remote_count)

        delete_prefix(client, final_prefix)
        promote_prefix(client, stage_prefix, final_prefix)

    except SystemExit:
        raise
    except Exception as exc:
        try:
            delete_prefix(_s3_client(), stage_prefix)
        except Exception:
            pass
        common.die(logger, bucket, error="s3 archive failed", detail=str(exc))
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)

    logger.info(common.kv_fields(
        status="success", bucket=bucket, index=index, dest=dest, files=expected))
    sys.exit(0)


if __name__ == "__main__":
    main()
