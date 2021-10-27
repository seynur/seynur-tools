#### Documentation

**python3 restore-archive-for-splunk.py --help**


usage: restore-archive-for-splunk.py [-h] [-a ARCHIVE_PATH] [-r RESTORE_PATH] [-i RESTORE_INDEX] [-s START_DATE] [-e END_DATE] [-sh SPLUNK_HOME] [--restart_splunk] [--check_integrity] [--version]

optional arguments:

  -h, --help            show this help message and exit
  
  --restart_splunk      Splunk needs to be restarted to complete the rebuilding process
  
  --check_integrity     Checks the integrity of buckets to be rebuild
  
  --version             show program's version number and exit

arguments:

  -a ARCHIVE_PATH, --archive_path ARCHIVE_PATH
                        Archive path where the frozen buckets are
                        
  -r RESTORE_PATH, --restore_path RESTORE_PATH
                        The path where the frozen buckets are moved to rebuild
                        
  -i RESTORE_INDEX, --restore_index RESTORE_INDEX
                        The index name where the buckets are rebuilt
                        
  -s START_DATE, --start_date START_DATE
                        The starting date of the logs to be returned from the archive
                        
  -e END_DATE, --end_date END_DATE
                        The end date of logs to be returned from the archive
                        
  -sh SPLUNK_HOME, --splunk_home SPLUNK_HOME
                        Splunk home path

 example:

    archive_path:   "/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
    restore_path:   "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    restore_index:  "archive_wineventlog"
    start_date:     "Datetime format "%Y-%m-%d %H:%M:%S""
    end_date:       "Datetime format "%Y-%m-%d %H:%M:%S""
    splunk_home:    "/opt/splunk"

    python3 splunk_restore_archive.py  -a "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -r "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i "archive_wineventlog" -s "2021-03-13 00:00:00" -e "2021-03-16 00:00:00" -sh "/opt/splunk" --restart_splunk --check_integrity

    python3 splunk_restore_archive.py  --archive_path "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --restore_path "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --restore_index "archive_wineventlog" --start_date "2021-03-13 00:00:00" --end_date "2021-03-16 00:00:00" --splunk_home "/opt/splunk"

    python3 splunk_restore_archive.py  -a="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -r="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    -i="archive_wineventlog" -s="2021-03-13 00:00:00" -e="2021-03-16 00:00:00" -sh="/opt/splunk"  --check_integrity

    python3 splunk_restore_archive.py  --archive_path="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --restore_path="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
    --restore_index="archive_wineventlog" --start_date="2021-03-13 00:00:00" --end_date="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --restart_splunk


