import os
import time
import shutil
import subprocess
import sys
import argparse
import re
from datetime import datetime
import json

def handle_dates(oldest_time,newest_time):
    '''Returns start and end datetime in int.
    Converts datetime to epoch to find correct buckets.
    '''
    epoch_time = []
    for date in [oldest_time,newest_time]:
        try:
            date = time.strptime(date, "%Y-%m-%d %H:%M:%S")
            epoch_time.append(int(time.mktime(date).__str__().split(".")[0]))
        except ValueError as e:
            print(f"Error: Invalid date format '{date}'. Expected format: '%Y-%m-%d %H:%M:%S'. Error: {e}")
            sys.exit(1)
    
    if len(epoch_time) != 2:
        print(f"Error: Expected 2 dates, but processed {len(epoch_time)} dates")
        sys.exit(1)
        
    return epoch_time[0], epoch_time[1]


def find_buckets(source_path, oldest_epoch_time, newest_epoch_time):
    '''Returns the list buckets_found.
    Finds buckets in source path according to oldest and newest epoch time.

    Keyword arguments:
    source_path -- archive path (frozendb)
    oldest_epoch_time -- oldest date
    newest_epoch_time -- newest date
    '''
    try:
        bucket_list = os.listdir(source_path)
    except (OSError, FileNotFoundError) as e:
        print(f"Error: Cannot access source path '{source_path}': {e}")
        return []

    buckets_found = []
    for i in bucket_list:
        bucket = i.split("_", maxsplit=3)

        # Skip invalid bucket names
        if len(bucket) < 4:
            print(f"Warning: Skipping bucket '{i}' - unexpected format (expected: index_epoch1_epoch2_randomid)")
            continue

        try:
            newest_bucket_epoch_time = int(bucket[1])
            oldest_bucket_epoch_time = int(bucket[2])
        except (ValueError, IndexError) as e:
            print(f"Warning: Skipping bucket '{i}' - invalid epoch time format: {e}")
            continue

        if (newest_bucket_epoch_time >= oldest_epoch_time and oldest_bucket_epoch_time <= newest_epoch_time):
            buckets_found.append(i)

    print("---------------------------")
    print(f"The number of bucket(s) found in the local path: {len(buckets_found)}.")
    return buckets_found


def find_oldest_and_newest_bucket_dates(buckets_found, source_path="", index=""):
    '''Finds oldest and newest date of the buckets for specific index.'''
    bucket_dates = [tuple(map(int, bucket.split("_")[1:3])) for bucket in buckets_found]
    oldest_epoch_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(min(d[0] for d in bucket_dates)))
    newest_epoch_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max(d[1] for d in bucket_dates)))

    if not index and source_path:
        if len(source_path.split("/"))>0:
            index = source_path.split("/")[-1] if len(source_path.split("/")[-1])>0 else source_path.split("/")[-2]
        elif len(source_path.split("\\"))>0:
            index = source_path.split("\\")[-1] if len(source_path.split("\\")[-1])>0 else source_path.split("\\")[-2]

    print("---------------------------")
    print(f"For '{index}' index")
    print(f"Oldest date: '{oldest_epoch_time}', newest date: '{newest_epoch_time}'.\n")


def restore_buckets_from_s3(index, frozendb, oldest_epoch_time, newest_epoch_time, bucket_name, s3_endpoint=""):
    '''Lists and restores buckets from S3 (default or custom endpoint).'''
    print("---------------------------")

    list_cmd = [
        "aws", "s3api", "list-objects",
        "--bucket", bucket_name,
        "--query", "Contents[].{Key: Key, Size: Size}"
    ]

    if s3_endpoint != "":
        print(f"Listing and filtering S3 buckets from custom endpoint: {s3_endpoint}")
        list_cmd += ["--endpoint-url", s3_endpoint]
    else:
        print("Listing and filtering S3 buckets from default AWS endpoint...")

    try:
        result = subprocess.check_output(list_cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"Error listing S3 buckets: {e.output}")
        sys.exit(1)

    try:
        objects = json.loads(result)
    except json.JSONDecodeError:
        print("Failed to parse S3 list output.")
        return []

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

    print(f"The number of bucket(s) found in S3: {len(matched_keys)}.\n")
    
    if oldest_epoch_time == 0:
        matched_dbbucket_names = [key.split("/")[1] for key in matched_keys]
        index = key.split("/")[0]
        return index, matched_dbbucket_names
    else:
        for key in matched_keys:
            local_path = os.path.join(frozendb, os.path.dirname(key))
            os.makedirs(local_path, exist_ok=True)
            full_local_file_path = os.path.join(frozendb, key)
            print(f"Downloading {key} to {full_local_file_path}")
            get_cmd = ["aws", "s3api", "get-object", "--bucket", bucket_name, "--key", key, full_local_file_path]
            if s3_endpoint:
                get_cmd += ["--endpoint-url", s3_endpoint]
            subprocess.run(get_cmd)


def copy_buckets(source_path, dest_path, buckets_found):
    '''Copies buckets from frozendb to thaweddb.'''
    print("---------------------------")
    print("Copying Buckets...")
    for bucket in buckets_found:
        source_file = source_path + bucket
        destination = dest_path + bucket
        shutil.copytree(source_file, destination)
    print("Buckets are successfully moved...")
    print("---------------------------")
    return None


def check_data_integrity(source_path, buckets_found, splunk_home):
    '''Checks data integrity of buckets one by one.'''
    path = os.getcwd()
    buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity = [], [], []
    buckets_to_process = buckets_found

    for bucket in buckets_found:
        bucket_path = source_path + bucket + "/rawdata/"
        for filename in os.listdir(bucket_path):
            if not filename.startswith("l2Hash") and (int(len(os.listdir(bucket_path)) < 3)):
                buckets_not_checked_integrity.append(bucket)
            os.chdir(path)
    buckets_to_process = list(set(buckets_to_process) - set(buckets_not_checked_integrity))

    subprocess.run(["cd", f"{(splunk_home + '/bin') or '/opt/splunk/bin'}"])
    for bucket in buckets_to_process:
        bucket_path = source_path + bucket
        integrity_result = subprocess.check_output(
            [f"{splunk_home}/bin/splunk check-integrity -bucketPath {bucket_path}"],
            shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
        print(integrity_result)
        match = re.findall(r'succeeded=(\d),\sfailed=(\d)', integrity_result)
        if not match:
            print(f"Warning: Could not parse integrity result for bucket '{bucket}'.")
            buckets_failed_integrity.append(bucket)
            continue
        fail = int(match[0][1])
        if fail == 1:
            buckets_failed_integrity.append(bucket)
            print(f"Integrity check failed for {bucket}")
        else:
            buckets_passed_integrity.append(bucket)

    print("Data integrity check completed.")
    print(f"Failed: {len(buckets_failed_integrity)}, Passed: {len(buckets_passed_integrity)}, No Check: {len(buckets_not_checked_integrity)}")
    buckets_found = list(set(buckets_found) - set(buckets_failed_integrity))
    os.chdir(path)
    return buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity


def log_data_integrity(buckets_not_checked_integrity, buckets_failed_integrity, buckets_passed_integrity, splunk_home):
    '''Logs integrity results to file.'''
    path = os.getcwd()
    log_path = splunk_home + "/var/log/splunk/"
    os.makedirs(log_path, exist_ok=True)
    os.chdir(log_path)

    file_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S_integrity_check.log")
    with open(file_name, "w+") as f:
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\r\n\r\n")
        f.write("---- Buckets Failed ----\r\n")
        for b in buckets_failed_integrity:
            f.write(f"- {b}\r\n")
        f.write("\n---- Buckets Passed ----\r\n")
        for b in buckets_passed_integrity:
            f.write(f"- {b}\r\n")
        f.write("\n---- No Integrity Check ----\r\n")
        for b in buckets_not_checked_integrity:
            f.write(f"- {b}\r\n")
    os.chdir(path)
    return None


def rebuild_buckets(buckets_found, dest_path, dest_index, splunk_home):
    '''Rebuilds buckets in thaweddb.'''
    buckets_failed, buckets_passed = [], []
    path = os.getcwd()
    subprocess.run(["cd", f"{(splunk_home + '/bin') or '/opt/splunk/bin'}"], stdout=subprocess.PIPE)
    for bucket in buckets_found:
        try:
            subprocess.check_output(
                [f"{splunk_home}/bin/splunk rebuild {dest_path}{bucket} {dest_index}"],
                shell=True, universal_newlines=True)
            buckets_passed.append(bucket)
        except subprocess.CalledProcessError as e:
            print(f"Error rebuilding bucket '{bucket}': {e}")
            buckets_failed.append(bucket)
    os.chdir(path)
    print("---------------------------")
    print("Buckets rebuild completed.")
    print(f"Success: {len(buckets_passed)}, Failed: {len(buckets_failed)}")
    print("---------------------------")
    return buckets_passed, buckets_failed


def restart_splunk(splunk_home):
    '''Restarts the Splunk instance.'''
    print("Restarting Splunk...")
    subprocess.run(["cd", f"{(splunk_home + '/bin') or '/opt/splunk/bin'}"])
    result = subprocess.check_output(f"{splunk_home}/bin/splunk restart", shell=True, universal_newlines=True)
    print(result)
    return None


def archive_help():
    '''Argument parser for the script.'''
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-f", "--frozendb", type=str, help="Path where frozen buckets are stored")
    parser.add_argument("-t", "--thaweddb", type=str, help="Path to rebuild (thaweddb)")
    parser.add_argument("-i", "--index", type=str, help="Index name for rebuilding")
    parser.add_argument("-o", "--oldest_time", type=str, help="Oldest log time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("-n", "--newest_time", type=str, help="Newest log time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("-s", "--splunk_home", type=str, help="Splunk home path")
    parser.add_argument("--restart_splunk", action='store_const', const=restart_splunk)
    parser.add_argument("--check_integrity", action='store_const', const=check_data_integrity)
    parser.add_argument("-s3", "--s3_path", type=str, help="S3 custom endpoint")
    parser.add_argument("-s3b", "--s3_default_bucket", type=str, help="Default S3 bucket name")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0", help="show program's version number and exit")
    return parser.parse_args()


def main():
    args = archive_help()
    if args.newest_time and args.oldest_time:
        oldest_epoch_time, newest_epoch_time = handle_dates(args.oldest_time, args.newest_time)
        # buckets_found = find_buckets(args.frozendb, oldest_epoch_time, newest_epoch_time)
        frozendb = args.frozendb + args.index + "/"

        if args.check_integrity and not args.s3_path:
            buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity = \
                check_data_integrity(args.frozendb, buckets_found, args.splunk_home)
            log_data_integrity(buckets_not_checked_integrity, buckets_failed_integrity, buckets_passed_integrity, args.splunk_home)

        if args.s3_default_bucket:
            args.s3_path = args.s3_path if args.s3_path else ""
            restore_buckets_from_s3(args.index, args.frozendb, oldest_epoch_time, newest_epoch_time, args.s3_default_bucket, args.s3_path)
            buckets_found = find_buckets(frozendb, oldest_epoch_time, newest_epoch_time)
            
        else:
            buckets_found = find_buckets(frozendb, oldest_epoch_time, newest_epoch_time)

        copy_buckets(frozendb, args.thaweddb, buckets_found)

        buckets_passed, buckets_failed = rebuild_buckets(buckets_found, args.thaweddb, args.index, args.splunk_home)
        if args.restart_splunk:
            restart_splunk(args.splunk_home)
    else:
        newest_epoch_time = int(time.time())
        if args.s3_default_bucket:
            args.s3_path = args.s3_path if args.s3_path else ""
            index, buckets_found = restore_buckets_from_s3(args.index, args.frozendb, 0, newest_epoch_time, args.s3_default_bucket, args.s3_path)
            find_oldest_and_newest_bucket_dates(buckets_found, index=index)
        else:
            buckets_found = find_buckets(args.frozendb, 0, newest_epoch_time)
            find_oldest_and_newest_bucket_dates(buckets_found, source_path=args.frozendb)


if __name__ == "__main__":
    main()



#     python3 /Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /splunk_restore_archive_merged.py --frozendb="/Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /lolo_s3/" --thaweddb="/Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /lolo_tha/"
# --index="oyku_test" --oldest_time="2021-03-13 00:00:00" --newest_time="2025-11-12 00:00:00" --splunk_home="/Users/oyku/dev/splunk/splunks/splunk_9-3-2/splunk_20250515" --s3_default_bucket="s3-frozen-test-bucket"  --s3_path="http://localhost:4566"


# python3 /Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /splunk_restore_archive_merged.py --frozendb="/Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /lolo_s3/" --index="oyku_test" --s3_default_bucket="s3-frozen-test-bucket" --s3_path="http://localhost:4566"


# python3 /Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /restore-archive-for-splunk.py --frozendb="/Users/oyku/dev/github/seynur/restore-archive-for-splunk/restore-archive-for-splunk.py /lolo_s3/" --index="oyku_test" --s3_default_bucket="s3-frozen-test-bucket" --s3_path="http://localhost:4566"