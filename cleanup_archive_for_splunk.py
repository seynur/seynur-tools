import os
import time
import shutil
import subprocess
import sys
import argparse
import itertools


def take_args():
    """Returns all the arguments in str.
    Takes the arguments from the shell.
    Prints the arguments and sleeps for 3 seconds for users to read.

    """
    archive_path = sys.argv[1] # Archive path for finding duplicate buckets.
    opt_params = ["show_command", "remove_command", "move_command", "moving_path"] # Optional parameters (show/remove/move/moving_path)
    for i in range(len(opt_params)):
        try:
             opt_params[i] = sys.argv[i+2]
        except IndexError:
             opt_params[i] = None
        if opt_params[i] != None:
            command = opt_params[i]  # Show/Remove/Move duplicate buckets.
    moving_path = opt_params[3] # The folder path to move duplicate buckets.
    print("Command:", command)
    print("---------------------------")
    print("Moving Path:", moving_path)
    print("---------------------------")
    time.sleep(3)
    return archive_path, command, moving_path


def compare_buckets(archive_path):
    '''Returns the list of original, replicated, single, and all buckets.
    Finds and compares all buckets in archive path with each other and finds out duplicate buckets.

    Keyword arguments:
    archive_path -- archive path for finding duplicate buckets

    '''
    bucket_list = os.listdir(archive_path)

    duplicate_buckets_db = []
    duplicate_buckets_rb = []
    dublicate_buckets = []
    indexes = []
    single_indexes = []
    single_buckets =[]

    for (i_index,i),(j_index,j) in itertools.combinations(enumerate(bucket_list), 2):
        #print((i_index,i),(j_index,j) , bucket_list[i_index])
        i = i.split("_", maxsplit=1)[1]
        j = j.split("_", maxsplit=1)[1]
        if i == j:
            indexes.append(i_index)
            indexes.append(j_index)
            dublicate_buckets.append(bucket_list[i_index])
            dublicate_buckets.append(bucket_list[j_index])
        else:
            single_indexes.append(i_index)
            single_indexes.append(j_index)

    single_indexes = list(dict.fromkeys(single_indexes))
    single_indexes = list(set(single_indexes) - set(indexes))
    print("single_indexes",single_indexes)
    print("indexes",indexes)
    for element in single_indexes:
        single_buckets.append(bucket_list[element])
    print("single_buckets",single_buckets)
    for element in dublicate_buckets:
        bucket = element.split("_", maxsplit=1)[0]
        if bucket == "db":
            duplicate_buckets_db.append(element)
        elif bucket == "rb":
            duplicate_buckets_rb.append(element)

    print("duplicate_buckets_db",duplicate_buckets_db)
    print("duplicate_buckets_rb",duplicate_buckets_rb)

    print("The number of buckets found: {}.".format(len(bucket_list)))
    print("The number of orginal buckets found: {}.".format(len(duplicate_buckets_db)))
    print("The number of replicated buckets found: {}.".format(len(duplicate_buckets_rb)))
    print("The number of single buckets found: {}.".format(len(single_buckets)))
    print("single + original + replicated =", len(single_buckets) + len(duplicate_buckets_rb) + len(duplicate_buckets_db))

    return single_buckets, duplicate_buckets_db, duplicate_buckets_rb, bucket_list



def clean_buckets(command, duplicate_buckets_rb, moving_path, archive_path):
    '''Returns None.
        Shows/moves/removes the duplicate buckets.

        Keyword arguments:
        command -- required operation on buckets (shows/moves/removes)
        duplicate_buckets_rb -- replicated duplicate buckets
        moving_path -- if the command is move, replicated duplicate buckets will be moved.
        archive_path -- archive path for finding duplicate buckets

        '''
    if command == "show":
        print("---------------------------")
        print("The number of buckets:", len(duplicate_buckets_rb))
        print("Duplicate bucket list:")
        print(duplicate_buckets_rb)
    elif command == "move":
        print("---------------------------")
        print("The number of buckets:", len(duplicate_buckets_rb))
        print("Moving Buckets...")
        for bucket in duplicate_buckets_rb:
            source_file = archive_path + bucket
            destination = moving_path + bucket
            print(source_file,destination)
            #shutil.copytree(source_file, destination)
            shutil.move(source_file, destination, copy_function=shutil.copytree)
        print("---------------------------")
        print("Buckets are successfully moved...")
    elif command == "remove":
        print("---------------------------")
        print("The number of buckets:", len(duplicate_buckets_rb))
        print("Deleting Buckets...")
        for bucket in duplicate_buckets_rb:
            source_file = archive_path + bucket + "/"
            shutil.rmtree(source_file)
        print("---------------------------")
        print("Duplicate buckets are successfully deleted...")
    return None


def cleanup_help():
    '''Returns None.
    The argparse module also automatically generates help and usage.

    '''

    example_text = ''' example:

    archive_path:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    command:        "move"
    moving_path:    "/archive_buckets/indexes/wineventlog/"

    python3 cleanup_archive_for_splunk.py "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" "move" "/archive_buckets/indexes/wineventlog/"

    '''

    parser = argparse.ArgumentParser(epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("<archive_path>", type=str, help="Archive path where the frozen buckets are")
    parser.add_argument("<command>", type=str, help="Required operation on buckets which are show, move, and remove")
    parser.add_argument("<moving_path>", type=str, help="Moving path for the duplicate buckets. It is used if the command is 'move'")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0.0')
    args = parser.parse_args()
    return None



def main():
    cleanup_help()
    archive_path, command, moving_path = take_args()
    single_buckets, duplicate_buckets_db, duplicate_buckets_rb, bucket_list = compare_buckets(archive_path)
    clean_buckets(command, duplicate_buckets_rb, moving_path, archive_path)



if __name__ == "__main__":
    main()
