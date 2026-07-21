#!/bin/bash
#
# find_old_frozen_buckets.sh
#
# Scans a Splunk frozen-bucket archive directory and reports buckets
# whose data is older than a given age threshold (default: 2 years),
# based on the "oldest event" epoch timestamp embedded in the bucket name.
#
# Splunk frozen bucket naming convention:
#   db_<newest_epoch>_<oldest_epoch>_<bucket_id>[_<guid>]
#   rb_<newest_epoch>_<oldest_epoch>_<bucket_id>[_<guid>]  (rebuilt buckets)
#
# Usage:
#   ./find_old_frozen_buckets.sh [archive_dir] [age_in_days]
#
# Defaults:
#   archive_dir = /data/frozen
#   age_in_days = 730 (2 years)
#
# Intended to be run via cron, e.g.:
#   0 3 * * * /path/to/find_old_frozen_buckets.sh /data/frozen 730 >> /var/log/splunk_archive_audit.log 2>&1

set -euo pipefail

ARCHIVE_DIR="${1:-/data/frozen}"
AGE_DAYS="${2:-730}"

NOW_EPOCH=$(date +%s)
THRESHOLD_EPOCH=$(( NOW_EPOCH - (AGE_DAYS * 86400) ))

echo "=============================================="
echo " Splunk Frozen Bucket Age Audit"
echo " Run time         : $(date)"
echo " Archive directory: ${ARCHIVE_DIR}"
echo " Age threshold    : ${AGE_DAYS} days (cutoff epoch: ${THRESHOLD_EPOCH})"
echo "=============================================="

if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "ERROR: Archive directory '$ARCHIVE_DIR' does not exist or is not accessible."
    exit 1
fi

FOUND=0
TOTAL_SIZE=0

# Loop through directories matching Splunk bucket naming pattern
while IFS= read -r -d '' bucket; do
    bucket_name=$(basename "$bucket")

    # Extract fields by splitting on underscore
    # Expected: db_<newest>_<oldest>_<id>[_<guid>]
    IFS='_' read -r prefix newest oldest bucket_id guid <<< "$bucket_name"

    # Validate that 'oldest' is a proper epoch integer
    if ! [[ "$oldest" =~ ^[0-9]+$ ]]; then
        echo "SKIP (unparseable name): $bucket_name"
        continue
    fi

    if [ "$oldest" -lt "$THRESHOLD_EPOCH" ]; then
        oldest_human=$(date -d "@${oldest}" '+%Y-%m-%d' 2>/dev/null || date -r "${oldest}" '+%Y-%m-%d')
        size=$(du -sh "$bucket" 2>/dev/null | cut -f1)
        size_kb=$(du -sk "$bucket" 2>/dev/null | cut -f1)
        TOTAL_SIZE=$(( TOTAL_SIZE + size_kb ))
        FOUND=$(( FOUND + 1 ))
        echo "OLD BUCKET: $bucket_name  (path=${bucket}, oldest_event=${oldest_human}, size=${size})"
    fi
done < <(find "$ARCHIVE_DIR" -mindepth 1 -maxdepth 2 -type d \( -name 'db_*' -o -name 'rb_*' \) -print0)

echo "----------------------------------------------"
if [ "$FOUND" -eq 0 ]; then
    echo "No buckets older than ${AGE_DAYS} days found."
else
    echo "Total buckets older than ${AGE_DAYS} days: ${FOUND}"
    echo "Total size: ${TOTAL_SIZE} KB"
fi
echo "=============================================="
