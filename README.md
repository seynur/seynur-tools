#### Documentation

**python3 splunk_restore_archive.py --help**


usage: splunk_restore_archive.py [-h] [--version]
                                 <archive_path> <restore_path> <restore_index>
                                 <start_date> <end_date> <splunk_restart>

positional arguments:
  <archive_path>    Archive path where the frozen buckets are
  <restore_path>    The path where the frozen buckets are moved to rebuild
  <restore_index>   The index name where the buckets are rebuilt
  <start_date>      The starting date of the logs to be returned from the
                    archive
  <end_date>        The end date of logs to be returned from the archive
  <splunk_restart>  Splunk needs to be restarted to complete the rebuilding
                    process

optional arguments:
  -h, --help        show this help message and exit
  --version         show program's version number and exit

 example:

    archive_path:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    restore_path:   "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    restore_index:  "archive_wineventlog"
    start_date:     "Datetime format "%Y-%m-%d %H:%M:%S""
    end_date:       "Datetime format "%Y-%m-%d %H:%M:%S""
    splunk_restart: "splunk restart"

    python3 "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    "archive_wineventlog" "2021-03-13 00:00:00" "2021-03-16 00:00:00" "splunk restart"



**python3 cleanup_archive_for_splunk.py --help**


usage: cleanup_archive_for_splunk.py [-h] [--version]
                                     <archive_path> <command> <moving_path>

positional arguments:
  <archive_path>  Archive path where the frozen buckets are
  <command>       Required operation on buckets which are show, move, and
                  remove
  <moving_path>   Moving path for the duplicate buckets. It is used if the
                  command is 'move'

optional arguments:
  -h, --help      show this help message and exit
  --version       show program's version number and exit

 example:

    archive_path:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    command:        "move"
    moving_path:    "/archive_buckets/indexes/wineventlog/"

    python3 cleanup_archive_for_splunk.py "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" "move" "/archive_buckets/indexes/wineventlog/"
