#!/usr/bin/env python3
import sys, os, subprocess

# Define the base GCS path where journal.zst files will be uploaded
# ex: "gs://my-bucket/frozen_buckets"
GCS_BUCKET = "gs://<GCS-PATH>"

# Set to the local fake-gcs-server endpoint for local testing; leave empty for production
# ex: EMULATOR_HOST = "http://localhost:4443"
EMULATOR_HOST = ""

def archive_journal_to_gcs(bucket_path, index_name, bucket_name):
    journal_path = os.path.join(bucket_path, "rawdata", "journal.zst")

    if not os.path.isfile(journal_path):
        print(f"[SKIP] journal.zst not found at {journal_path}")
        return

    gcs_dest_path = f"{GCS_BUCKET}/{index_name}/{bucket_name}/rawdata/journal.zst"
    print(f"Uploading {journal_path} → {gcs_dest_path}")

    try:
        if EMULATOR_HOST:
            _upload_via_emulator(journal_path, index_name, bucket_name)
        else:
            subprocess.check_call(["gsutil", "cp", journal_path, gcs_dest_path])
        print("[OK] Upload complete.")
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        sys.exit(1)

def _upload_via_emulator(journal_path, index_name, bucket_name):
    import urllib.request, urllib.parse
    bucket_name_gcs = GCS_BUCKET.replace("gs://", "").split("/")[0]
    blob_path = f"{index_name}/{bucket_name}/rawdata/journal.zst"
    encoded = urllib.parse.quote(blob_path, safe="")
    url = f"{EMULATOR_HOST}/upload/storage/v1/b/{bucket_name_gcs}/o?uploadType=media&name={encoded}"
    with open(journal_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    urllib.request.urlopen(req)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python coldToGCS.py <bucket_path>")

    bucket_path = sys.argv[1]

    if not os.path.isdir(bucket_path):
        sys.exit(f"[ERROR] Invalid bucket path: {bucket_path}")

    index_name = os.path.basename(os.path.dirname(os.path.dirname(bucket_path)))
    bucket_name = os.path.basename(bucket_path)

    archive_journal_to_gcs(bucket_path, index_name, bucket_name)
