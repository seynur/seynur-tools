import os
import time
import shutil
import subprocess
import sys
import argparse
import re
from datetime import datetime


def handle_dates(oldest_time,newest_time):
    '''Returns start and end datetime in int.
    Converts datetime to epoch to find correct buckets.

    Keyword arguments:
    oldest_time -- oldest date ("%Y-%m-%d %H:%M:%S")
    newest_time -- newest date ("%Y-%m-%d %H:%M:%S")
    '''
    epoch_time = []
    for date in [oldest_time,newest_time]:
        try:
            date = time.strptime(date, "%Y-%m-%d %H:%M:%S")
            epoch_time.append(int(time.mktime(date).__str__().split(".")[0]))
        except ValueError as e:
            print(f"Error: Invalid date format '{date}'. Expected format: '%Y-%m-%d %H:%M:%S'. Error: {e}")
            sys.exit(1)
    
    # Ensure we have exactly 2 epoch times
    if len(epoch_time) != 2:
        print(f"Error: Expected 2 dates, but processed {len(epoch_time)} dates")
        sys.exit(1)
        
    oldest_epoch_time = epoch_time[0]
    newest_epoch_time = epoch_time[1]
    return oldest_epoch_time, newest_epoch_time


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
        # Check if bucket name has the expected format (at least 4 parts: index_epoch1_epoch2_randomid)
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
    print("The number of buckets found: {}.".format(len(buckets_found)))
    return buckets_found


def find_oldest_and_newest_bucket_dates(source_path, buckets_found):
    '''Returns the list oldest_and_newest_bucket_dates.
    Finds oldest and newest date of the buckets for specifix index.

    Keyword arguments:
    source_path -- archive path (frozendb)
    buckets_found -- buckets found
    oldest_epoch_time -- oldest date (epoch) 
    newest_epoch_time -- newest date (epoch)
    '''    

    bucket_dates = [tuple(map(int, bucket.split("_")[1:3])) for bucket in buckets_found]
    oldest_epoch_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(min(d[0] for d in bucket_dates)))
    newest_epoch_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(max(d[1] for d in bucket_dates)))

    try:
        source_path = source_path.split("/")[-1]
    except:
        source_path = source_path.split("\\")[-1]

    print("---------------------------")
    print("For \'{}\' index".format(source_path))
    print("oldest date : \'{}\' and newest date \'{}\'.\n".format(oldest_epoch_time, newest_epoch_time))



def copy_buckets(source_path, dest_path,buckets_found):
    '''Returns None.
    Moves buckets from source path (frozendb) to destination path (thaweddb).

    Keyword arguments:
    source_path -- archive path (frozendb)
    dest_path -- the path where the buckets are moved to rebuild (thaweddb)
    buckets_found -- buckets found
    '''
    print("---------------------------")
    print("Copying Buckets...")
    for bucket in buckets_found:
        source_file = source_path + bucket
        destination = dest_path + bucket
        shutil.copytree(source_file, destination)
    print("---------------------------")
    print("Buckets are successfully moved...")
    print("---------------------------")
    return None

def check_data_integrity(source_path, buckets_found, splunk_home):
    '''Returns buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity.
    Checks the data integrity one by one in the source path (thaweddb).


    Keyword arguments:
    source_path -- archive path (frozendb)
    buckets_found -- buckets found
    splunk_home -- splunk home path
    '''
    path = os.getcwd()
    buckets_failed_integrity = []
    buckets_passed_integrity = []
    buckets_not_checked_integrity = []
    buckets_to_process = buckets_found
    for bucket in buckets_found:
        bucket_path = source_path + bucket + "/rawdata/"
        for filename in os.listdir(bucket_path):
            if not filename.startswith("l2Hash") and (int(len(os.listdir(bucket_path))<3)):
                buckets_not_checked_integrity.append(bucket)
            os.chdir(path)
    buckets_to_process = list(set(buckets_to_process) - set(buckets_not_checked_integrity))

    subprocess.run(["cd","{}".format((splunk_home + "/bin") or ("/opt/splunk/bin"))])
    for bucket in buckets_to_process:
        bucket_path = source_path + bucket
        intregrity_result = subprocess.check_output(["{}/bin/splunk {} -bucketPath {}".format(splunk_home, "check-integrity", bucket_path)], shell = True, stderr=subprocess.STDOUT, universal_newlines = True)
        print(intregrity_result)
        match = re.findall(r'succeeded=(\d),\sfailed=(\d)', intregrity_result)
        
        # Check if regex found a match
        if not match:
            print(f"Warning: Could not parse integrity result for bucket '{bucket}'. Adding to failed list.")
            buckets_failed_integrity.append(bucket)
            continue
            
        try:
            fail = int(match[0][1])
        except (ValueError, IndexError) as e:
            print(f"Warning: Error parsing integrity result for bucket '{bucket}': {e}. Adding to failed list.")
            buckets_failed_integrity.append(bucket)
            continue
            
        if fail == 1:
            buckets_failed_integrity.append(bucket)
            print("Integrity check has failed for the bucket:", bucket)
            print("This bucket will be removed from rebuilding list...")
        else:
            buckets_passed_integrity.append(bucket)
    print("Data integrity is checked...")
    print("Results:")
    print("The number of buckets has failed:", len(buckets_failed_integrity))
    print("---------------------------")
    print("The number of buckets has succeed:", len(buckets_passed_integrity))
    print("---------------------------")
    print("The number of buckets have no data ingtegrity control:", len(buckets_not_checked_integrity))
    print("---------------------------")
    buckets_found = list(set(buckets_found) - set(buckets_failed_integrity))
    print("The number of buckets will be rebuild:", len(buckets_passed_integrity) + len(buckets_not_checked_integrity))
    print("---------------------------")
    os.chdir(path)
    return buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity


def log_data_integrity(buckets_not_checked_integrity, buckets_failed_integrity, buckets_passed_integrity, splunk_home):
    '''Returns None.
    Creates a log file about failed, passed and buckets without data integrity control.


    Keyword arguments:
    buckets_not_checked_integrity -- buckets do not have data integrity control
    buckets_failed_integrity -- buckets failed the integrity check
    buckets_passed_integrity -- buckets passed the integrity check
    '''
    path = os.getcwd()
    log_path = "/var/log/splunk/"
    splunk_log_path = splunk_home + log_path
    if os.path.exists("logs"):
        os.chdir("logs")
    else:
        os.chdir(splunk_log_path)

    file_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S_integrity_check.log")
    f = open(file_name, "w+")
    f.write("Timestamp: {}\r\n\r\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    f.write("------------------\r\n")
    f.write("  Buckets Failed  \r\n")
    f.write("------------------\r\n\r\n")
    for i, bucket in zip(range(len(buckets_failed_integrity)), buckets_failed_integrity):
        f.write("{}- {}\r\n".format(i+1,bucket))
    f.write("\r\n\r\n\r\n")
    f.write("------------------\r\n")
    f.write("  Buckets Passed  \r\n")
    f.write("------------------\r\n\r\n")
    for i, bucket in zip(range(len(buckets_passed_integrity)), buckets_passed_integrity):
        f.write("{}- {}\r\n".format(i+1,bucket))
    f.write("\r\n\r\n\r\n")
    f.write("----------------------------------------\r\n")
    f.write("  Buckets Have No Data Integrity Check  \r\n")
    f.write("----------------------------------------\r\n\r\n")
    for i, bucket in zip(range(len(buckets_not_checked_integrity)), buckets_not_checked_integrity):
        f.write("{}- {}\r\n".format(i+1,bucket))
    f.close()
    os.chdir(path)
    return None


def rebuild_buckets(buckets_found, dest_path, dest_index, splunk_home):
    '''Returns failed and passed buckets.
    Rebuilds the buckets one by one in the destination path (thaweddb).

    Keyword arguments:
    buckets_found -- buckets found
    dest_path -- the path where the buckets are moved to rebuild (thaweddb)
    dest_index -- the index name where the buckets will be rebuilt
    splunk_home -- splunk home path
    '''
    buckets_failed = []
    buckets_passed = []
    path = os.getcwd()
    subprocess.run(["cd","{}".format((splunk_home + "/bin") or ("/opt/splunk/bin"))], stdout=subprocess.PIPE)
    for bucket in buckets_found:
        try:
            subprocess.check_output(["{}/bin/splunk rebuild {}{} {}".format(splunk_home, dest_path, bucket, dest_index)], shell = True, universal_newlines = True)
            buckets_passed.append(bucket)
        except subprocess.CalledProcessError as e:
            print(f"Error rebuilding bucket '{bucket}': {e}")
            buckets_failed.append(bucket)
    os.chdir(path)
    print("Buckets are rebuilt...")
    print("---------------------------")
    print("The number of buckets that rebuilt successfully:", len(buckets_passed))
    print("---------------------------")
    print("The number of buckets that failed to rebuild:", len(buckets_failed))
    print("---------------------------")
    return buckets_passed, buckets_failed


def log_rebuilt_results(buckets_passed, buckets_failed, splunk_home):
    '''Returns None.
    Logs the failed and passed buckets names.

    Keyword arguments:
    buckets_passed -- buckets that are rebuilt successfully
    buckets_failed -- buckets that failed the rebuilding process

    '''

    path = os.getcwd()
    log_path="/var/log/splunk/"
    splunk_log_path= splunk_home + log_path
    if os.path.exists("logs"):
        os.chdir("logs")
    else:
        os.chdir(splunk_log_path)

    file_name = datetime.now().strftime("%Y-%m-%d-%H-%M-%S_buckets_rebuilt.log")
    f = open(file_name, "w+")
    f.write("Timestamp: {}\r\n\r\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    f.write("--------------------------------\r\n")
    f.write("  Buckets Successfully Rebuilt \r\n")
    f.write("-------------------------------\r\n\r\n")
    for i, bucket in zip(range(len(buckets_passed)), buckets_passed):
        f.write("{}- {}\r\n".format(i+1,bucket))
    f.write("\r\n\r\n\r\n")
    f.write("-----------------------------\r\n")
    f.write("  Buckets Failed to Rebuild \r\n")
    f.write("-----------------------------\r\n\r\n")
    for i, bucket in zip(range(len(buckets_failed)), buckets_failed):
        f.write("{}- {}\r\n".format(i + 1, bucket))
    f.close()
    os.chdir(path)
    return None


def restart_splunk(splunk_home):
    '''Returns None.
    Restarts the Splunk instance.

    Keyword arguments:
    splunk_home -- splunk home path
    '''
    print("Restarting Splunk now...")
    subprocess.run(["cd", "{}".format((splunk_home + "/bin") or ("/opt/splunk/bin"))])
    restart_result = subprocess.check_output("{}/bin/{}".format(splunk_home, "splunk restart"), shell=True, universal_newlines=True)
    print(restart_result)
    return None


def archive_help():
    '''Returns None.
    The argparse module also automatically generates help and usage.

    '''

    example_text = ''' example:

    frozendb:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    thaweddb:   "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    index:  "archive_wineventlog"
    oldest_time:     "Datetime format "%Y-%m-%d %H:%M:%S""
    newest_time:       "Datetime format "%Y-%m-%d %H:%M:%S""
    splunk_home:    "/opt/splunk"

    python3 splunk_restore_archive.py  -f "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i "archive_wineventlog" -o "2021-03-13 00:00:00" -n "2021-03-16 00:00:00" -s "/opt/splunk" --restart_splunk --check_integrity

    python3 splunk_restore_archive.py  --frozendb "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --index "archive_wineventlog" --oldest_time "2021-03-13 00:00:00" --newest_time "2021-03-16 00:00:00" --splunk_home "/opt/splunk"

    python3 splunk_restore_archive.py  -f="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i="archive_wineventlog" -o="2021-03-13 00:00:00" -n="2021-03-16 00:00:00" -s="/opt/splunk"  --check_integrity

    python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --index="archive_wineventlog" --oldest_time="2021-03-13 00:00:00" --newest_time="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --restart_splunk

    for learning oldest-newest date, try below example:
    python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    '''

    parser = argparse.ArgumentParser(epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    required_args = parser.add_argument_group("arguments")
    required_args.add_argument("-f","--frozendb", type=str, help="Frozendb path where the frozen buckets are")
    parser.add_argument("-t", "--thaweddb", type=str, help="The path where the frozen buckets are moved to rebuild")
    parser.add_argument("-i", "--index", type=str, help="The index name where the buckets are rebuilt")
    parser.add_argument("-o", "--oldest_time", type=str, help="The oldest date of the logs to be returned from the archive")
    parser.add_argument("-n", "--newest_time", type=str, help="The newest date of logs to be returned from the archive")
    parser.add_argument("-s", "--splunk_home", type=str,help="Splunk home path")
    parser.add_argument("--restart_splunk", action='store_const', const=restart_splunk, help="Splunk needs to be restarted to complete the rebuilding process")
    parser.add_argument("--check_integrity", action='store_const', const=check_data_integrity, help="Checks the integrity of buckets to be rebuild")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    args = parser.parse_args()
    return args


def main():
    args = archive_help()
    if args.newest_time and args.oldest_time:
        oldest_epoch_time, newest_epoch_time = handle_dates(args.oldest_time, args.newest_time)
        buckets_found = find_buckets(args.frozendb, oldest_epoch_time, newest_epoch_time)
        if args.check_integrity:
            buckets_found, buckets_failed_integrity, buckets_passed_integrity, buckets_not_checked_integrity = check_data_integrity(args.frozendb, buckets_found, args.splunk_home)
            log_data_integrity(buckets_not_checked_integrity, buckets_failed_integrity, buckets_passed_integrity, args.splunk_home)
        copy_buckets(args.frozendb, args.thaweddb, buckets_found)
        buckets_passed, buckets_failed = rebuild_buckets(buckets_found, args.thaweddb, args.index, args.splunk_home)
        log_rebuilt_results(buckets_passed, buckets_failed, args.splunk_home)
        if args.restart_splunk:
            restart_splunk(args.splunk_home)

    else:
        newest_epoch_time = int(time.time())
        buckets_found = find_buckets(args.frozendb, 0, newest_epoch_time)
        print(buckets_found)
        buckets_found = find_oldest_and_newest_bucket_dates(args.frozendb, buckets_found)


if __name__ == "__main__":
    main()