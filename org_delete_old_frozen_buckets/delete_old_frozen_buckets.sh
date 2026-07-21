#!/bin/bash
#
# delete_old_frozen_buckets.sh
#
# Deletes Splunk frozen buckets older than a given age threshold (default: 2 years),
# based on the "oldest event" epoch timestamp embedded in the bucket name.
#
# Splunk frozen bucket naming convention:
#   db_<newest_epoch>_<oldest_epoch>_<bucket_id>[_<guid>]
#   rb_<newest_epoch>_<oldest_epoch>_<bucket_id>[_<guid>]
#
# SAFETY: Defaults to DRY RUN. Nothing is deleted unless you pass --delete explicitly.
#
# Usage:
#   ./delete_old_frozen_buckets.sh [archive_dir] [age_in_days] [--delete]
#
# Examples:
#   ./delete_old_frozen_buckets.sh /data/frozen 730            # dry run, just lists what WOULD be deleted
#   ./delete_old_frozen_buckets.sh /data/frozen 730 --delete    # actually deletes
#
# Cron example (after you've validated dry-run output manually):
#   0 4 * * * /path/to/delete_old_frozen_buckets.sh /data/frozen 730 --delete >> /var/log/splunk_archive_cleanup.log 2>&1

set -euo pipefail

ARCHIVE_DIR="${1:-/data/frozen}"
AGE_DAYS="${2:-730}"
MODE="${3:-}"

DELETE_MODE=false
if [ "$MODE" == "--delete" ]; then
    DELETE_MODE=true
fi

NOW_EPOCH=$(date +%s)
THRESHOLD_EPOCH=$(( NOW_EPOCH - (AGE_DAYS * 86400) ))

echo "=============================================="
echo " Splunk Frozen Bucket Cleanup"
echo " Run time         : $(date)"
echo " Archive directory: ${ARCHIVE_DIR}"
echo " Age threshold    : ${AGE_DAYS} days (cutoff epoch: ${THRESHOLD_EPOCH})"
if [ "$DELETE_MODE" = true ]; then
    echo " Mode             : DELETE (files will be permanently removed)"
else
    echo " Mode             : DRY RUN (no files will be deleted)"
fi
echo "=============================================="

if [ ! -d "$ARCHIVE_DIR" ]; then
    echo "ERROR: Archive directory '$ARCHIVE_DIR' does not exist or is not accessible."
    exit 1
fi

FOUND=0
TOTAL_SIZE_KB=0

while IFS= read -r -d '' bucket; do
    bucket_name=$(basename "$bucket")

    IFS='_' read -r prefix newest oldest bucket_id guid <<< "$bucket_name"

    if ! [[ "$oldest" =~ ^[0-9]+$ ]]; then
        echo "SKIP (unparseable name): $bucket_name"
        continue
    fi

    if [ "$oldest" -lt "$THRESHOLD_EPOCH" ]; then
        oldest_human=$(date -d "@${oldest}" '+%Y-%m-%d' 2>/dev/null || date -r "${oldest}" '+%Y-%m-%d')
        size=$(du -sh "$bucket" 2>/dev/null | cut -f1)
        size_kb=$(du -sk "$bucket" 2>/dev/null | cut -f1)
        TOTAL_SIZE_KB=$(( TOTAL_SIZE_KB + size_kb ))
        FOUND=$(( FOUND + 1 ))

        if [ "$DELETE_MODE" = true ]; then
            rm -rf -- "$bucket"
            echo "DELETED: $bucket_name  (path=${bucket}, oldest_event=${oldest_human}, size=${size})"
        else
            echo "WOULD DELETE: $bucket_name  (path=${bucket}, oldest_event=${oldest_human}, size=${size})"
        fi
    fi
done < <(find "$ARCHIVE_DIR" -mindepth 1 -maxdepth 2 -type d \( -name 'db_*' -o -name 'rb_*' \) -print0)

echo "----------------------------------------------"
if [ "$FOUND" -eq 0 ]; then
    echo "No buckets older than ${AGE_DAYS} days found."
else
    if [ "$DELETE_MODE" = true ]; then
        echo "Total buckets deleted: ${FOUND}"
    else
        echo "Total buckets that WOULD be deleted: ${FOUND}"
        echo "(Re-run with --delete to actually remove them)"
    fi
    echo "Total size: ${TOTAL_SIZE_KB} KB"
fi
echo "=============================================="
