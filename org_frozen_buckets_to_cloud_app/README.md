# Splunk Cold Buckets Archival Scripts: GCS & AWS S3

This repository provides two Python scripts designed to be used as Splunk `coldToFrozenScript` for archiving frozen buckets to cloud storage:

- `coldToGCS.py`: Uploads only `rawdata/journal.zst` file from each cold bucket to a Google Cloud Storage (GCS) bucket.
- `coldToS3.py`: Uploads only `rawdata/journal.zst` file from each cold bucket to an AWS S3 bucket or S3 with custom endpoint.


! Don't forget to copy python scripts to customize your bucket names.

---

## 🔧 Prerequisites

### Common Splunk Settings (`indexes.conf`)

In the index stanza (e.g., `index_name`), use:

```ini
[index_name]
homePath = $SPLUNK_DB/index_name/db
coldPath = $SPLUNK_DB/index_name/colddb
thawedPath = $SPLUNK_DB/index_name/thaweddb
coldToFrozenScript =  "$SPLUNK_HOME/bin/python" "$SPLUNK_HOME/etc/apps/org_frozen_buckets_to_cloud_app/bin/coldToS3.py"
frozenTimePeriodInSecs = 2592000
```

---

## ☁️ Google Cloud Setup

### 1. Install and Configure GCloud CLI

```bash
brew install google-cloud-sdk  # macOS
sudo apt install google-cloud-sdk  # Debian/Ubuntu
```

### 2. Authenticate and Initialize

```bash
gcloud init
gcloud auth login
```

Alternatively, use a service account:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-service-account.json"
```

### 3. Create the GCS Bucket (if not already)

```bash
gsutil mb gs://your-bucket-name
```

### 4. Grant Permissions

Ensure your authenticated user or service account has at least:

- `Storage Object Creator`
- `Storage Object Viewer`

---

## ☁️ AWS S3 Setup (for custom S3)

### 1. Install and Configure AWS CLI

```bash
brew install awscli  # macOS
sudo apt install awscli  # Debian/Ubuntu

add all configurations into ~/.bashrc file
-- export AWS_ACCESS_KEY_ID="<AWS-ACCESS-KEY-ID>"
-- export AWS_SECRET_ACCESS_KEY="<AWS-SECRET-ACCESS-KEY>"
```

### 2. IAM Permissions

Attach the following policy to the IAM user:

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::your-bucket-name",
    "arn:aws:s3:::your-bucket-name/*"
  ]
}
```

### 3. Create the S3 Bucket

```bash
aws s3 mb s3://your-bucket-name
```

---

## 📜 Scripts Overview

### coldToGCS.py

Uploads:
```
gs://your-bucket/your_prefix/index_name/bucket_id/rawdata/journal.zst
```

Requires:
- `gsutil` available in PATH
- Proper GCloud auth or service account

### coldToS3.py

The default script expects a custom endpoint. If you want to use the default AWS S3 URLs, simply put line 9 in the comment line.

Uploads:
```
s3://your-bucket/your_prefix/index_name/bucket_id/rawdata/journal.zst
```

Requires:
- `boto3` installed via `pip install boto3`
- AWS credentials via `aws configure` or environment variables

---

## 🧪 Testing Bucket Transition

1. Add test events to your index
2. Force hot bucket to roll:

```bash
curl -k -u admin:changeme https://localhost:8089/services/data/indexes/YOUR_INDEX/roll-hot-buckets -X POST
```

3. Watch Splunk logs:

```bash
tail -f $SPLUNK_HOME/var/log/splunk/splunkd.log | grep ArchiveProcessor
```

---

## 📂 Folder Structure Example

```
your_splunk_app/
├── bin/
│   ├── coldToGCS.py
│   └── coldToS3.py
├── README.md
└── default/
    └── indexes.conf
```

---

Happy Archiving! 📦☁️
