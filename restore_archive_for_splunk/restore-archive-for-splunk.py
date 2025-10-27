#!/usr/bin/env python3
"""
Splunk Archive Restore Tool

This script restores archived/frozen Splunk data from local storage or S3.
It includes security improvements, proper logging, and a new bucket listing feature.
"""

import os
import time
import shutil
import subprocess
import sys
import argparse
import re
from datetime import datetime
import json
import logging
from typing import List, Tuple, Optional
from pathlib import Path

# Configuration constants
DEFAULT_SPLUNK_HOME = "/opt/splunk"
DEFAULT_SPLUNK_BIN = "/opt/splunk/bin"
DEFAULT_LOG_PATH = "/var/log/splunk/"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_SEPARATOR = "\\r\\n\\r\\n\\r\\n"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('restore_archive.log')
    ]
)
logger = logging.getLogger(__name__)


def validate_paths(*paths: str) -> None:
    """Validate that all provided paths exist."""
    for path in paths:
        if path and not os.path.exists(path):
            print(f"Error: Path does not exist: {path}")
            logger.error(f"Path validation failed: {path}")
            sys.exit(1)


def validate_splunk_binary(splunk_home: str) -> None:
    """Validate that Splunk binary exists."""
    splunk_bin = os.path.join(splunk_home, "bin", "splunk")
    if not os.path.exists(splunk_bin):
        print(f"Error: Splunk binary not found at: {splunk_bin}")
        logger.error(f"Splunk binary validation failed: {splunk_bin}")
        sys.exit(1)


def validate_aws_cli() -> None:
    """Validate that AWS CLI is available."""
    try:
        subprocess.run(["aws", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: AWS CLI not found. Please install AWS CLI for S3 operations.")
        logger.error("AWS CLI validation failed")
        sys.exit(1)


def handle_dates(oldest_time: str, newest_time: str) -> Tuple[int, int]:
    """Returns start and end datetime in int.
    Converts datetime to epoch to find correct buckets.

    Args:
        oldest_time: oldest date ("%Y-%m-%d %H:%M:%S")
        newest_time: newest date ("%Y-%m-%d %H:%M:%S")
    
    Returns:
        Tuple of (oldest_epoch_time, newest_epoch_time)
    """
    epoch_time = []
    for date in [oldest_time, newest_time]:
        try:
            date = time.strptime(date, DATE_FORMAT)
            epoch_time.append(int(time.mktime(date)))
        except ValueError as e:
            print(f"Error: Invalid date format '{date}'. Expected format: '{DATE_FORMAT}'. Error: {e}")
            logger.error(f"Date parsing failed: {date} - {e}")
            sys.exit(1)
    
    # Ensure we have exactly 2 epoch times
    if len(epoch_time) != 2:
        print(f"Error: Expected 2 dates, but processed {len(epoch_time)} dates")
        logger.error(f"Date processing failed: expected 2 dates, got {len(epoch_time)}")
        sys.exit(1)
        
    oldest_epoch_time = epoch_time[0]
    newest_epoch_time = epoch_time[1]
    return oldest_epoch_time, newest_epoch_time


def find_buckets(source_path: str, oldest_epoch_time: int, newest_epoch_time: int) -> List[str]:
    """Returns the list buckets_found.
    Finds buckets in source path according to oldest and newest epoch time.

    Args:
        source_path: archive path (frozendb)
        oldest_epoch_time: oldest date
        newest_epoch_time: newest date
    
    Returns:
        List of bucket names found
    """
    try:
        bucket_list = os.listdir(source_path)
    except OSError as e:
        print(f"Error: Cannot access source path '{source_path}': {e}")
        logger.error(f"Source path access failed: {source_path} - {e}")
        return []
    
    buckets_found = []
    for i in bucket_list:
        bucket = i.split("_", maxsplit=3)
        # Check if bucket name has the expected format (at least 4 parts: index_epoch1_epoch2_randomid)
        if len(bucket) < 4:
            logger.warning(f"Skipping bucket '{i}' - unexpected format (expected: index_epoch1_epoch2_randomid)")
            continue
        try:
            newest_bucket_epoch_time = int(bucket[1])
            oldest_bucket_epoch_time = int(bucket[2])
        except (ValueError, IndexError) as e:
            logger.warning(f"Skipping bucket '{i}' - invalid epoch time format: {e}")
            continue
        if (newest_bucket_epoch_time >= oldest_epoch_time and oldest_bucket_epoch_time <= newest_epoch_time):
            buckets_found.append(i)
    
    logger.info("---------------------------")
    logger.info(f"The number of buckets found: {len(buckets_found)}.")
    return buckets_found


def find_oldest_and_newest_bucket_dates(buckets_found: List[str], source_path: str = "", index: str = "") -> None:
    """Returns the list oldest_and_newest_bucket_dates.
    Finds oldest and newest date of the buckets for specific index.

    Args:
        source_path: archive path (frozendb)
        buckets_found: buckets found
        index: index name
    """    
    bucket_dates = [tuple(map(int, bucket.split("_")[1:3])) for bucket in buckets_found]
    oldest_epoch_time = time.strftime(DATE_FORMAT, time.localtime(min(d[0] for d in bucket_dates)))
    newest_epoch_time = time.strftime(DATE_FORMAT, time.localtime(max(d[1] for d in bucket_dates)))

    if index == "":
        try:
            index = source_path.split("/")[-1]
        except (IndexError, ValueError):
            index = source_path.split("\\")[-1]

    logger.info("---------------------------")
    logger.info(f"For '{index}' index")
    logger.info(f"oldest date : '{oldest_epoch_time}' and newest date '{newest_epoch_time}'.\n")


def list_available_buckets(path: str) -> None:
    """
    Lists available buckets in the specified path with detailed information.
    
    Args:
        path: Path to scan for buckets (frozendb or thaweddb)
    """
    if not os.path.exists(path):
        print(f"Error: Path does not exist: {path}")
        logger.error(f"List buckets path validation failed: {path}")
        return
    
    try:
        bucket_list = os.listdir(path)
    except OSError as e:
        print(f"Error: Cannot access path '{path}': {e}")
        logger.error(f"List buckets path access failed: {path} - {e}")
        return
    
    bucket_info = []
    
    for bucket_name in bucket_list:
        bucket_path = os.path.join(path, bucket_name)
        if not os.path.isdir(bucket_path):
            continue
            
        # Parse bucket name to extract epoch times
        bucket_parts = bucket_name.split("_", maxsplit=3)
        if len(bucket_parts) < 4:
            continue
            
        try:
            start_epoch = int(bucket_parts[1])
            end_epoch = int(bucket_parts[2])
            
            # Convert to human readable dates
            start_date = time.strftime(DATE_FORMAT, time.localtime(start_epoch))
            end_date = time.strftime(DATE_FORMAT, time.localtime(end_epoch))
            
            # Calculate bucket size
            total_size = 0
            file_count = 0
            rawdata_path = os.path.join(bucket_path, "rawdata")
            
            if os.path.exists(rawdata_path):
                for root, dirs, files in os.walk(rawdata_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                            file_count += 1
                        except OSError:
                            continue
            
            # Convert size to human readable format
            if total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
            
            bucket_info.append({
                'name': bucket_name,
                'start_date': start_date,
                'end_date': end_date,
                'size': size_str,
                'file_count': file_count,
                'start_epoch': start_epoch
            })
            
        except (ValueError, IndexError):
            continue
    
    # Sort by start epoch time (oldest first)
    bucket_info.sort(key=lambda x: x['start_epoch'])
    
    # Display results
    logger.info("=" * 120)
    logger.info("AVAILABLE BUCKETS")
    logger.info("=" * 120)
    logger.info(f"{'Bucket Name':<50} {'Start Date':<20} {'End Date':<20} {'Size':<10} {'Files':<8}")
    logger.info("-" * 120)
    
    for bucket in bucket_info:
        logger.info(f"{bucket['name']:<50} {bucket['start_date']:<20} {bucket['end_date']:<20} {bucket['size']:<10} {bucket['file_count']:<8}")
    
    logger.info("-" * 120)
    logger.info(f"Total buckets found: {len(bucket_info)}")
    logger.info("=" * 120)


def restore_buckets_from_s3(index: str, frozendb: str, oldest_epoch_time: int, newest_epoch_time: int, bucket_name: str, s3_endpoint: str = "") -> Optional[Tuple[str, List[str]]]:
    """
    Lists objects in the given S3 bucket and downloads matching frozen buckets by epoch time range.

    Args:
        index: Index name
        s3_endpoint: The S3 endpoint URL (e.g., http://localhost:4566), or "" for default AWS
        frozendb: Local frozendb destination path
        oldest_epoch_time: Start epoch time
        newest_epoch_time: End epoch time
        bucket_name: S3 bucket name 
    
    Returns:
        Tuple of (index, matched_bucket_names) or None if error
    """
    logger.info("---------------------------")

    # Build the list-objects command
    list_cmd = [
        "aws", "s3api", "list-objects",
        "--bucket", bucket_name,
        "--query", "Contents[].{Key: Key, Size: Size}"
    ]
    
    logger.info(s3_endpoint)
    if s3_endpoint != "":
        logger.info(f"Listing and filtering S3 buckets from custom endpoint: {s3_endpoint}")
        list_cmd += ["--endpoint-url", s3_endpoint]
    else:
        logger.info("Listing and filtering S3 buckets from default AWS endpoint...")

    try:
        result = subprocess.check_output(list_cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to list S3 buckets: {e.output}")
        logger.error(f"S3 list objects failed: {e}")
        sys.exit(1)

    try:
        objects = json.loads(result)
    except json.JSONDecodeError:
        print("Error: Failed to parse S3 list output.")
        logger.error("S3 JSON parsing failed")
        return None

    matched_keys = []
    for obj in objects:
        key = obj["Key"]
        if key[0:key.find("/")] == index:
            match = re.search(r'db_(\d+)_(\d+)_\d+/rawdata/journal\.zst$', key)
            if not match:
                continue
            start_epoch, end_epoch = int(match.group(1)), int(match.group(2))
            if end_epoch >= oldest_epoch_time and start_epoch <= newest_epoch_time:
                matched_keys.append(key)

    logger.info(f"Found {len(matched_keys)} matching bucket(s) in S3.")
    
    if oldest_epoch_time == 0:
        matched_dbbucket_names = []
        for key in matched_keys:
            matched_dbbucket_names.append(key.split("/")[1])
            
        index = key.split("/")[0]
        return index, matched_dbbucket_names
    else:
        # Download matched buckets
        for key in matched_keys:
            local_path = os.path.join(frozendb, os.path.dirname(key))
            os.makedirs(local_path, exist_ok=True)
            full_local_file_path = os.path.join(frozendb, key)
            logger.info(f"Downloading {key} to {full_local_file_path}")

            get_cmd = [
                "aws", "s3api", "get-object",
                "--bucket", bucket_name,
                "--key", key,
                full_local_file_path
            ]
            if s3_endpoint:
                get_cmd += ["--endpoint-url", s3_endpoint]

            try:
                subprocess.run(get_cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error: Failed to download {key}: {e}")
                logger.error(f"S3 download failed: {key} - {e}")
                continue


def copy_buckets(source_path: str, dest_path: str, buckets_found: List[str]) -> None:
    """Returns None.
    Moves buckets from source path (frozendb) to destination path (thaweddb).

    Args:
        source_path: archive path (frozendb)
        dest_path: the path where the buckets are moved to rebuild (thaweddb)
        buckets_found: buckets found
    """
    logger.info("---------------------------")
    logger.info("Copying Buckets...")
    for i, bucket in enumerate(buckets_found, 1):
        logger.info(f"Processing bucket {i}/{len(buckets_found)}: {bucket}")
        source_file = os.path.join(source_path, bucket)
        destination = os.path.join(dest_path, bucket)
        try:
            shutil.copytree(source_file, destination)
        except Exception as e:
            print(f"Error: Failed to copy bucket {bucket}: {e}")
            logger.error(f"Bucket copy failed: {bucket} - {e}")
            continue
    logger.info("---------------------------")
    logger.info("Buckets are successfully moved...")
    logger.info("---------------------------")


def check_data_integrity(source_path: str, buckets_found: List[str], splunk_home: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Returns buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity.
    Checks the data integrity one by one in the source path (thaweddb).

    Args:
        source_path: archive path (frozendb)
        buckets_found: buckets found
        splunk_home: splunk home path
    
    Returns:
        Tuple of (buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity)
    """
    buckets_failed_integrity = []
    buckets_passed_integrity = []
    buckets_not_checked_integrity = []
    buckets_to_process = buckets_found
    
    # Check for buckets without proper data structure
    for bucket in buckets_found:
        bucket_path = os.path.join(source_path, bucket, "rawdata")
        if os.path.exists(bucket_path):
            files = os.listdir(bucket_path)
            if not any(filename.startswith("l2Hash") for filename in files) and len(files) < 3:
                buckets_not_checked_integrity.append(bucket)
    
    buckets_to_process = list(set(buckets_to_process) - set(buckets_not_checked_integrity))
    
    # Check integrity for valid buckets
    splunk_bin = os.path.join(splunk_home, "bin")
    for bucket in buckets_to_process:
        bucket_path = os.path.join(source_path, bucket)
        try:
            cmd = [os.path.join(splunk_bin, "splunk"), "check-integrity", "-bucketPath", bucket_path]
            integrity_result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            logger.info(integrity_result)
            
            match = re.findall(r'succeeded=(\d),\sfailed=(\d)', integrity_result)
            
            if not match:
                logger.warning(f"Could not parse integrity result for bucket '{bucket}'. Adding to failed list.")
                buckets_failed_integrity.append(bucket)
                continue
            
            try:
                fail = int(match[0][1])
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing integrity result for bucket '{bucket}': {e}. Adding to failed list.")
                buckets_failed_integrity.append(bucket)
                continue
            
            if fail == 1:
                buckets_failed_integrity.append(bucket)
                logger.warning(f"Integrity check has failed for the bucket: {bucket}")
                logger.warning("This bucket will be removed from rebuilding list...")
            else:
                buckets_passed_integrity.append(bucket)
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to run integrity check for bucket '{bucket}': {e}")
            logger.error(f"Integrity check subprocess failed: {bucket} - {e}")
            buckets_failed_integrity.append(bucket)
        except Exception as e:
            print(f"Error: Unexpected error during integrity check for bucket '{bucket}': {e}")
            logger.error(f"Integrity check unexpected error: {bucket} - {e}")
            buckets_failed_integrity.append(bucket)
    
    logger.info("Data integrity is checked...")
    logger.info("Results:")
    logger.info(f"The number of buckets has failed: {len(buckets_failed_integrity)}")
    logger.info("---------------------------")
    logger.info(f"The number of buckets has succeed: {len(buckets_passed_integrity)}")
    logger.info("---------------------------")
    logger.info(f"The number of buckets have no data integrity control: {len(buckets_not_checked_integrity)}")
    logger.info("---------------------------")
    buckets_found = list(set(buckets_found) - set(buckets_failed_integrity))
    logger.info(f"The number of buckets will be rebuild: {len(buckets_passed_integrity) + len(buckets_not_checked_integrity)}")
    logger.info("---------------------------")
    return buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity


def log_data_integrity(buckets_not_checked_integrity: List[str], buckets_failed_integrity: List[str], buckets_passed_integrity: List[str], splunk_home: str) -> None:
    """Returns None.
    Creates a log file about failed, passed and buckets without data integrity control.

    Args:
        buckets_not_checked_integrity: buckets do not have data integrity control
        buckets_failed_integrity: buckets failed the integrity check
        buckets_passed_integrity: buckets passed the integrity check
        splunk_home: splunk home path
    """
    log_path = os.path.join(splunk_home, DEFAULT_LOG_PATH)
    if os.path.exists("logs"):
        log_dir = "logs"
    else:
        log_dir = log_path
    
    os.makedirs(log_dir, exist_ok=True)
    file_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S_integrity_check.log")
    log_file_path = os.path.join(log_dir, file_name)
    
    with open(log_file_path, "w+") as f:
        f.write(f"Timestamp: {datetime.now().strftime(DATE_FORMAT)}\\r\\n\\r\\n")
        f.write("------------------\\r\\n")
        f.write("  Buckets Failed  \\r\\n")
        f.write("------------------\\r\\n\\r\\n")
        for i, bucket in enumerate(buckets_failed_integrity, 1):
            f.write(f"{i}- {bucket}\\r\\n")
        f.write(LOG_SEPARATOR)
        f.write("------------------\\r\\n")
        f.write("  Buckets Passed  \\r\\n")
        f.write("------------------\\r\\n\\r\\n")
        for i, bucket in enumerate(buckets_passed_integrity, 1):
            f.write(f"{i}- {bucket}\\r\\n")
        f.write(LOG_SEPARATOR)
        f.write("----------------------------------------\\r\\n")
        f.write("  Buckets Have No Data Integrity Check  \\r\\n")
        f.write("----------------------------------------\\r\\n\\r\\n")
        for i, bucket in enumerate(buckets_not_checked_integrity, 1):
            f.write(f"{i}- {bucket}\\r\\n")
    
    logger.info(f"Integrity check log written to: {log_file_path}")


def rebuild_buckets(buckets_found: List[str], dest_path: str, dest_index: str, splunk_home: str) -> Tuple[List[str], List[str]]:
    """Returns failed and passed buckets.
    Rebuilds the buckets one by one in the destination path (thaweddb).

    Args:
        buckets_found: buckets found
        dest_path: the path where the buckets are moved to rebuild (thaweddb)
        dest_index: the index name where the buckets will be rebuilt
        splunk_home: splunk home path
    
    Returns:
        Tuple of (buckets_passed, buckets_failed)
    """
    buckets_failed = []
    buckets_passed = []
    splunk_bin = os.path.join(splunk_home, "bin")
    
    for i, bucket in enumerate(buckets_found, 1):
        logger.info(f"Rebuilding bucket {i}/{len(buckets_found)}: {bucket}")
        bucket_path = os.path.join(dest_path, bucket)
        try:
            cmd = [os.path.join(splunk_bin, "splunk"), "rebuild", bucket_path, dest_index]
            subprocess.check_output(cmd, text=True)
            buckets_passed.append(bucket)
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to rebuild bucket '{bucket}': {e}")
            logger.error(f"Rebuild subprocess failed: {bucket} - {e}")
            buckets_failed.append(bucket)
        except Exception as e:
            print(f"Error: Unexpected error rebuilding bucket '{bucket}': {e}")
            logger.error(f"Rebuild unexpected error: {bucket} - {e}")
            buckets_failed.append(bucket)
    
    logger.info("Buckets are rebuilt...")
    logger.info("---------------------------")
    logger.info(f"The number of buckets that rebuilt successfully: {len(buckets_passed)}")
    logger.info("---------------------------")
    logger.info(f"The number of buckets that failed to rebuild: {len(buckets_failed)}")
    logger.info("---------------------------")
    return buckets_passed, buckets_failed


def log_rebuilt_results(buckets_passed: List[str], buckets_failed: List[str], splunk_home: str) -> None:
    """Returns None.
    Logs the failed and passed buckets names.

    Args:
        buckets_passed: buckets that are rebuilt successfully
        buckets_failed: buckets that failed the rebuilding process
        splunk_home: splunk home path
    """
    log_path = os.path.join(splunk_home, DEFAULT_LOG_PATH)
    if os.path.exists("logs"):
        log_dir = "logs"
    else:
        log_dir = log_path
    
    os.makedirs(log_dir, exist_ok=True)
    file_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S_buckets_rebuilt.log")
    log_file_path = os.path.join(log_dir, file_name)
    
    with open(log_file_path, "w+") as f:
        f.write(f"Timestamp: {datetime.now().strftime(DATE_FORMAT)}\\r\\n\\r\\n")
        f.write("--------------------------------\\r\\n")
        f.write("  Buckets Successfully Rebuilt \\r\\n")
        f.write("-------------------------------\\r\\n\\r\\n")
        for i, bucket in enumerate(buckets_passed, 1):
            f.write(f"{i}- {bucket}\\r\\n")
        f.write(LOG_SEPARATOR)
        f.write("-----------------------------\\r\\n")
        f.write("  Buckets Failed to Rebuild \\r\\n")
        f.write("-----------------------------\\r\\n\\r\\n")
        for i, bucket in enumerate(buckets_failed, 1):
            f.write(f"{i}- {bucket}\\r\\n")
    
    logger.info(f"Rebuild results log written to: {log_file_path}")


def restart_splunk(splunk_home: str) -> None:
    """Returns None.
    Restarts the Splunk instance.

    Args:
        splunk_home: splunk home path
    """
    logger.info("Restarting Splunk now...")
    splunk_bin = os.path.join(splunk_home, "bin")
    try:
        cmd = [os.path.join(splunk_bin, "splunk"), "restart"]
        restart_result = subprocess.check_output(cmd, text=True)
        logger.info(restart_result)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to restart Splunk: {e}")
        logger.error(f"Splunk restart failed: {e}")
        raise


def archive_help():
    """Returns None.
    The argparse module also automatically generates help and usage.
    """
    example_text = ''' example:

    frozendb:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    thaweddb:   "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    index:  "archive_wineventlog"
    oldest_time:     "Datetime format "%Y-%m-%d %H:%M:%S""
    newest_time:       "Datetime format "%Y-%m-%d %H:%M:%S""
    splunk_home:    "/opt/splunk"

    python3 restore-archive-for-splunk.py  -f "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i "archive_wineventlog" -o "2021-03-13 00:00:00" -n "2021-03-16 00:00:00" -s "/opt/splunk" --restart_splunk --check_integrity

    python3 restore-archive-for-splunk.py  --frozendb "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --index "archive_wineventlog" --oldest_time "2021-03-13 00:00:00" --newest_time "2021-03-16 00:00:00" --splunk_home "/opt/splunk"

    python3 restore-archive-for-splunk.py  -f="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i="archive_wineventlog" -o="2021-03-13 00:00:00" -n="2021-03-16 00:00:00" -s="/opt/splunk"  --check_integrity

    python3 restore-archive-for-splunk.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --index="archive_wineventlog" --oldest_time="2021-03-13 00:00:00" --newest_time="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --restart_splunk 

    for learning oldest-newest date, try below example:
    python3 restore-archive-for-splunk.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"

    for listing available buckets:
    python3 restore-archive-for-splunk.py  --list-buckets --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    '''

    parser = argparse.ArgumentParser(epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    required_args = parser.add_argument_group("arguments")
    required_args.add_argument("-f","--frozendb", type=str, help="Frozendb path where the frozen buckets are")
    parser.add_argument("-t", "--thaweddb", type=str, help="The path where the frozen buckets are moved to rebuild")
    parser.add_argument("-i", "--index", type=str, help="The index name where the buckets are rebuilt")
    parser.add_argument("-o", "--oldest_time", type=str, help="The oldest date of the logs to be returned from the archive")
    parser.add_argument("-n", "--newest_time", type=str, help="The newest date of logs to be returned from the archive")
    parser.add_argument("-s", "--splunk_home", type=str, help="Splunk home path")
    parser.add_argument("--restart_splunk", action='store_const', const=restart_splunk, help="Splunk needs to be restarted to complete the rebuilding process")
    parser.add_argument("--check_integrity", action='store_const', const=check_data_integrity, help="Checks the integrity of buckets to be rebuild")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    parser.add_argument("--s3_path", type=str, help="The S3 endpoint URL (e.g., http://localhost:4566)")
    parser.add_argument("--s3_default_bucket", type=str, help="Default S3 bucket name")
    parser.add_argument("--list-buckets", action='store_true', help="List available buckets in the specified path")
    args = parser.parse_args()
    return args


def main():
    args = archive_help()
    
    # Handle list-buckets functionality
    if args.list_buckets:
        if args.frozendb:
            logger.info(f"Listing buckets in frozendb: {args.frozendb}")
            list_available_buckets(args.frozendb)
        elif args.thaweddb:
            logger.info(f"Listing buckets in thaweddb: {args.thaweddb}")
            list_available_buckets(args.thaweddb)
        else:
            print("Error: --list-buckets requires either --frozendb or --thaweddb to be specified")
            logger.error("List buckets missing required path argument")
            sys.exit(1)
        return
    
    if args.newest_time and args.oldest_time:
        oldest_epoch_time, newest_epoch_time = handle_dates(args.oldest_time, args.newest_time)

        # Validate required paths and dependencies
        validate_paths(args.frozendb, args.thaweddb)
        validate_splunk_binary(args.splunk_home)
        
        if args.s3_default_bucket:
            validate_aws_cli()

        # Find buckets first before any integrity checks
        if args.s3_default_bucket:
            args.s3_path = args.s3_path if args.s3_path else ""
            restore_buckets_from_s3(args.index, args.frozendb, oldest_epoch_time, newest_epoch_time, args.s3_default_bucket, args.s3_path)
            frozendb = os.path.join(args.frozendb, args.index)
            buckets_found = find_buckets(frozendb, oldest_epoch_time, newest_epoch_time)      
        else:
            buckets_found = find_buckets(args.frozendb, oldest_epoch_time, newest_epoch_time)

        if args.check_integrity:
            buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity = check_data_integrity(args.frozendb, buckets_found, args.splunk_home)
            log_data_integrity(buckets_not_checked_integrity, buckets_failed_integrity, buckets_passed_integrity, args.splunk_home)

        # Copy buckets to thaweddb
        copy_buckets(args.frozendb, args.thaweddb, buckets_found)
        
        # Rebuild buckets
        buckets_passed, buckets_failed = rebuild_buckets(buckets_found, args.thaweddb, args.index, args.splunk_home)
        log_rebuilt_results(buckets_passed, buckets_failed, args.splunk_home)
        
        if args.restart_splunk:
            restart_splunk(args.splunk_home)

    else:
        newest_epoch_time = int(time.time())
        if args.s3_default_bucket:
            validate_aws_cli()
            args.s3_path = args.s3_path if args.s3_path else ""
            index, buckets_found = restore_buckets_from_s3(args.index, args.frozendb, 0, newest_epoch_time, args.s3_default_bucket, args.s3_path)
            logger.info(buckets_found)
            buckets_found = find_oldest_and_newest_bucket_dates(buckets_found, index=index)
        else:
            validate_paths(args.frozendb)
            buckets_found = find_buckets(args.frozendb, 0, newest_epoch_time)
            logger.info(buckets_found)
            buckets_found = find_oldest_and_newest_bucket_dates(buckets_found, source_path=args.frozendb)


if __name__ == "__main__":
    main()