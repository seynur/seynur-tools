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


usage: restore-archive-for-splunk.py [-h --help] [-f --frozendb] [-t --thaweddb] [-i --index]
                                     [-o --oldest_time] [-n --newest_time] [-s --splunk_home] [-s3 --s3_path] [-s3b --s3_default_bucket] [--restart_splunk] [--check_integrity] [--version] 

optional arguments:

  -h, --help                    show this help message and exit

  -f , --frozendb               Frozendb path where the frozen buckets are

  --restart_splunk              Splunk needs to be restarted to complete the rebuilding process

  --check_integrity             Checks the integrity of buckets to be rebuild

  --version                     show program's version number and exit

  -t, --thaweddb                The path where the frozen buckets are moved to rebuild

  -i, --index                   The index name where the buckets are rebuilt

  -o, --oldest_time             The starting date of the logs to be returned from the archive

  -n, --newest_time             The end date of logs to be returned from the archive

  -s, --splunk_home             Splunk home path

  -s3, --s3_path                The path where the frozen buckets are located in the S3

  -s3b, --s3_default_bucket     Default S3 bucket name


### Restore Archive 

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

You can restore frozen buckets from S3 with the command below:

```bash
python3 restore-archive-for-splunk.py --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
--index="archive_wineventlog" --oldest_time="2021-03-13 00:00:00" --newest_time="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --s3_default_bucket="s3-frozen-test-bucket" --restart_splunk
```

You can restore frozen buckets from custom S3 with the command below:

```bash
python3 restore-archive-for-splunk.py --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
--index="archive_wineventlog" --oldest_time="2021-03-13 00:00:00" --newest_time="2021-03-16 00:00:00" --splunk_home="/opt/splunk" --s3_path="http://localhost:4566" --s3_default_bucket="s3-frozen-test-bucket" --restart_splunk
```

### Oldest & Newest Datetime Finder
You can use the command below to find out what are the oldest & newest date times for the index.

On your local environmet:
```bash
python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"
```

On S3 Repository: 
```bash
python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"--index="wineventlog" --s3_default_bucket="s3-frozen-test-bucket"
```

On Custom S3 Repository:

```bash
python3 splunk_restore_archive.py  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" --index="wineventlog" --s3_path="http://localhost:4566" --s3_default_bucket="s3-frozen-test-bucket"
```

### Optional: Program version finder

```bash
python3 restore-archive-for-splunk.py  --version
```