# Documentation

## Directory Structure

```
restore_archive_for_splunk/
├── restore-archive-for-splunk.py    # Main script
├── README.md                        # Main documentation
├── LICENSE                          # License file
└── test/                           # Test subfolder
    ├── test_bucket_parsing.py      # Unit tests
    ├── create_test_data.py         # Test data generator
    ├── run_tests.py                # Test runner
    └── README.md                   # Detailed test documentation
```


## Running the script

You can create "logs" folder under your current directory or the logs will be written to splunk_home + "/var/log/splunk/" directory.

**python3 restore-archive-for-splunk.py --help**


usage: restore-archive-for-splunk.py [-h] [-f FROZENDB] [-t THAWEDDB] [-i INDEX]
                                     [-o OLDEST_TIME] [-n NEWEST_TIME] [-s SPLUNK_HOME]
                                     [--restart_splunk] [--check_integrity] [--version]

optional arguments:

  -h, --help            show this help message and exit

  --restart_splunk      Splunk needs to be restarted to complete the rebuilding process

  --check_integrity     Checks the integrity of buckets to be rebuild

  --version             show program's version number and exit

arguments:

  -f FROZENDB, --frozendb FROZENDB
                        Frozendb path where the frozen buckets are

  -t THAWEDDB, --thaweddb THAWEDDB
                        The path where the frozen buckets are moved to rebuild

  -i INDEX, --index INDEX
                        The index name where the buckets are rebuilt

  -o OLDEST_TIME, --oldest_time OLDEST_TIME
                        The starting date of the logs to be returned from the archive

  -n NEWEST_TIME, --newest_time NEWEST_TIME
                        The end date of logs to be returned from the archive

  -s SPLUNK_HOME, --splunk_home SPLUNK_HOME
                        Splunk home path


```bash
python3 splunk_restore_archive.py  -f "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
  -i "archive_wineventlog" -o "2021-03-13 00:00:00" -n "2021-03-16 00:00:00" -s "/opt/splunk" --restart_splunk --check_integrity
```

```bash
python3 splunk_restore_archive.py  --frozendb "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
--index "archive_wineventlog" --oldest_time "2021-03-13 00:00:00" --newest_time "2021-03-16 00:00:00" --splunk_home "/opt/splunk"
```

```bash
python3 splunk_restore_archive.py  -f="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" -t="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
-i="archive_wineventlog" -o="2021-03-13 00:00:00" -n="2021-03-16 00:00:00" -s="/opt/splunk"  --check_integrity
```

```bash
python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
--index="archive_wineventlog" --oldest_time="2021-03-13 00:00:00" --newest_time="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --restart_splunk
```

You can use the command below to find out what are the oldest & earliest date times for the index.

```bash
python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
```

## Testing

The project includes a comprehensive test suite to verify bucket parsing and validation logic. All test files are organized in the `test/` subfolder.

### Running Tests

```bash
cd test/

# Run all tests
python3 run_tests.py --all

# Run only unit tests
python3 run_tests.py --unit-tests

# Create test data
python3 run_tests.py --create-data
```

For detailed testing documentation, see `test/README.md` and `TEST_STRUCTURE.md`.