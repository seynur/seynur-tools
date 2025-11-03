#!/usr/bin/env python3
import os
import sys
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# === CONFIGURATION ===
S3_BUCKET_NAME = "<S3-BUCKET-NAME>"
LOCALSTACK_ENDPOINT = "http://<ENDPOINT-URL>:<ENDPOINT-PORT>"

def archive_journal_to_s3(bucket_path, index_name, bucket_name):
    journal_path = os.path.join(bucket_path, "rawdata", "journal.zst")

    if not os.path.isfile(journal_path):
        print(f"[SKIP] journal.zst not found at {journal_path}")
        return

    s3_key = f"{index_name}/{bucket_name}/rawdata/journal.zst"
    print(f"Uploading {journal_path} → s3://{S3_BUCKET_NAME}/{s3_key}")

    try:
        if LOCALSTACK_ENDPOINT:
            print("[INFO] Using LocalStack endpoint:", LOCALSTACK_ENDPOINT)
            s3 = boto3.client(
                "s3",
                endpoint_url=LOCALSTACK_ENDPOINT,
                aws_access_key_id="test",
                aws_secret_access_key="test",
                region_name="us-east-1"
            )
        else:
            print("[INFO] Using default S3 endpoint")
            s3 = boto3.client("s3")

        s3.upload_file(journal_path, S3_BUCKET_NAME, s3_key)
        print("[OK] Upload complete.")
        
    except (BotoCoreError, ClientError) as e:
        print(f"[ERROR] Upload failed: {e}")
        sys.exit(1)

# === ENTRY POINT ===
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python coldToS3.py <bucket_path>")

    bucket_path = sys.argv[1]

    if not os.path.isdir(bucket_path):
        sys.exit(f"[ERROR] Invalid bucket path: {bucket_path}")

    index_name = os.path.basename(os.path.dirname(os.path.dirname(bucket_path)))
    bucket_name = os.path.basename(bucket_path)

    archive_journal_to_s3(bucket_path, index_name, bucket_name) 