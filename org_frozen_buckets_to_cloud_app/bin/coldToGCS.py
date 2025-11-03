#!/usr/bin/env python3
import sys, os, subprocess

# Define the base GCS path where journal.zst files will be uploaded
GCS_BUCKET = "gs://<GCS-PATH>"

def archive_journal_to_gcs(bucket_path, index_name, bucket_name):
    # Construct the local path to the journal.zst file
    journal_path = os.path.join(bucket_path, "rawdata", "journal.zst")

    # If journal.zst doesn't exist, skip this bucket
    if not os.path.isfile(journal_path):
        print(f"[SKIP] journal.zst not found at {journal_path}")
        return

    # Construct the full GCS destination path
    gcs_dest_path = f"{GCS_BUCKET}/{index_name}/{bucket_name}/rawdata/journal.zst"

    print(f"Uploading {journal_path} → {gcs_dest_path}")
    try:
        # Use gsutil to copy the journal.zst file to the GCS path
        command = ["gsutil", "cp", journal_path, gcs_dest_path]
        subprocess.check_call(command)
        print("[OK] Upload complete.")
    except subprocess.CalledProcessError as e:
        # Exit with error if upload fails
        print(f"[ERROR] Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Ensure that a bucket path is provided as an argument
    if len(sys.argv) < 2:
        sys.exit("Usage: python coldToGCS.py <bucket_path>")

    bucket_path = sys.argv[1]

    # Validate that the given path is a valid directory
    if not os.path.isdir(bucket_path):
        sys.exit(f"[ERROR] Invalid bucket path: {bucket_path}")

    # Extract index name and bucket name from the directory structure
    index_name = os.path.basename(os.path.dirname(os.path.dirname(bucket_path)))
    bucket_name = os.path.basename(bucket_path)

    # Call the upload function
    archive_journal_to_gcs(bucket_path, index_name, bucket_name)