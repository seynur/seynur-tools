import os
import time
import shutil
import subprocess
import sys


def take_args():
    """Returns all the arguments in str.
    Takes the arguments from the shell and gets SPLUNK_HOME.
    Prints the arguments and sleeps for 3 seconds for users to read.

    """
    source_path = sys.argv[1] # Archive path for finding frozen buckets.
    dest_path = sys.argv[2] # The path where the buckets are moved to rebuild.
    dest_index = sys.argv[3] # The index name where the buckets are rebuilt
    start_date = sys.argv[4] # Datetime must be in this format  "%Y-%m-%d %H:%M:%S"
    end_date = sys.argv[5]
    splunk_restart = sys.argv[6]
    splunk_home = os.environ['SPLUNK_HOME']
    print("Source Path:", source_path)
    print("---------------------------")
    print("Destination Path:", dest_path)
    print("---------------------------")
    print("Destination Index:", dest_index)
    print("---------------------------")
    print("Start Date:", start_date)
    print("---------------------------")
    print("End Date:", end_date)
    time.sleep(3)
    print(type(splunk_home))
    return source_path, dest_path, dest_index, start_date, end_date, splunk_restart, splunk_home



def handle_dates(start_date,end_date):
    '''Returns start and end datetime in int.
    Converts datetime to epoch to find correct buckets.

    Keyword arguments:
    start_date -- start date ("%Y-%m-%d %H:%M:%S")
    end_date -- end date ("%Y-%m-%d %H:%M:%S")
    '''
    epoch_time = []
    for date in [start_date,end_date]:
        date = time.strptime(date, "%Y-%m-%d %H:%M:%S")
        epoch_time.append(int(time.mktime(date).__str__().split(".")[0]))
    start_epoch_time = epoch_time[0]
    end_epoch_time = epoch_time[1]
    return start_epoch_time, end_epoch_time

def find_buckets(source_path, start_epoch_time, end_epoch_time):
    '''Returns the list found_buckets.
    Finds buckets in source path according to start and end epoch time.

    Keyword arguments:
    source_path -- archive path (frozendb)
    start_epoch_time -- start date
    end_epoch_time -- end date
    '''
    bucket_list = os.listdir(source_path)
    found_buckets = []

    for i in bucket_list:
        bucket = i.split("_", maxsplit=3)
        end = int(bucket[1])
        start = int(bucket[2])
        if (end > start and start >= start_epoch_time and end <= end_epoch_time) or (start == end):
            found_buckets.append(i)
    print("---------------------------")
    print("The number of buckets found: {}.".format(len(found_buckets)))
    return found_buckets


def move_buckets(source_path, dest_path,found_buckets):
    '''Returns None.
    Moves buckets from source path (frozendb) to destination path (thaweddb).

    Keyword arguments:
    source_path -- archive path (frozendb)
    dest_path -- the path where the buckets are moved to rebuild (thaweddb)
    found_buckets -- buckets found
    '''
    print("---------------------------")
    print("Moving Buckets...")
    for bucket in found_buckets:
        source_file = source_path + bucket
        destination = dest_path + bucket
        shutil.copytree(source_file, destination)
    print("---------------------------")
    print("Buckets are successfully moved...")
    return None



def rebuild_buckets(found_buckets, dest_path, dest_index, splunk_home):
    '''Returns None.
    Rebuilds the buckets one by one in the destination path (thaweddb).

    Keyword arguments:
    found_buckets -- buckets found
    dest_path -- the path where the buckets are moved to rebuild (thaweddb)
    dest_index -- the index name where the buckets will be rebuilt
    splunk_home -- splunk home path
    '''
    subprocess.run(["cd","{}".format((splunk_home + "/bin") or ("/opt/splunk/bin"))])
    for bucket in found_buckets:
        rebuild_result = subprocess.check_output(["splunk rebuild {}{} {}".format(dest_path, bucket, dest_index)], shell = True, universal_newlines = True)
        print(rebuild_result)
        print("---------------------------")
    print("All buckets are rebuilt...")
    print("---------------------------")
    return None

def restart_splunk(splunk_home, splunk_restart):
    '''Returns None.
    Rebuilds the buckets one by one in the destination path (thaweddb).

    Keyword arguments:
    splunk_home -- splunk home path
    splunk_restart -- splunk restart
    '''
    print("Restarting Splunk now...")
    subprocess.run(["cd", "{}".format((splunk_home + "/bin") or ("/opt/splunk/bin"))])
    restart_result = subprocess.check_output("{}".format(splunk_restart), shell=True, universal_newlines=True)
    print(restart_result)
    return None


def main():
    source_path, dest_path, dest_index, start_date, end_date, splunk_restart, splunk_home = take_args()
    start_epoch_time, end_epoch_time = handle_dates(start_date, end_date)
    found_buckets = find_buckets(source_path, start_epoch_time, end_epoch_time)
    move_buckets(source_path, dest_path, found_buckets)
    rebuild_buckets(found_buckets, dest_path, dest_index, splunk_home)
    restart_splunk(splunk_home, splunk_restart)

if __name__ == "__main__":
    main()
