# Splunk Archive Restore Tool

A secure, production-ready Python script for restoring archived/frozen Splunk data from local storage or S3. This tool includes comprehensive error handling, logging, input validation, and a new bucket listing feature.

## 🚀 Features

- **Secure**: No shell injection vulnerabilities, proper subprocess handling
- **Reliable**: Comprehensive error handling and input validation
- **User-friendly**: Clear error messages and progress indicators
- **Flexible**: Support for local storage and S3 (including custom endpoints)
- **Informative**: Detailed logging and new bucket listing functionality
- **Tested**: Comprehensive test suite with 100% pass rate

## 📁 Directory Structure

```
restore_archive_for_splunk/
├── restore-archive-for-splunk.py    # Main script
├── README.md                        # This documentation
├── LICENSE                          # License file
└── test/                           # Test subfolder
    ├── test_bucket_parsing.py      # Unit tests
    ├── create_test_data.py         # Test data generator
    ├── run_tests.py                # Test runner
    └── README.md                   # Detailed test documentation
```

## 🛠️ Requirements

- Python 3.6+
- Splunk Enterprise (for integrity checks and rebuilding)
- AWS CLI (for S3 operations)

## 📋 Usage

### Help and Version

```bash
python3 restore-archive-for-splunk.py --help
python3 restore-archive-for-splunk.py --version
```

### List Available Buckets (NEW FEATURE)

View detailed information about available buckets in your archive:

```bash
# List buckets in frozendb
python3 restore-archive-for-splunk.py --list-buckets --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"

# List buckets in thaweddb
python3 restore-archive-for-splunk.py --list-buckets --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/"
```

The output includes:
- Bucket name
- Date range (human-readable format)
- Size (KB/MB/GB)
- File count in rawdata/
- Sorted by oldest date

### Restore Archive from Local Storage

```bash
# Basic restore with integrity check
python3 restore-archive-for-splunk.py \
  -f "/opt/splunk/var/lib/splunk/wineventlog/frozendb/" \
  -t "/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/" \
  -i "archive_wineventlog" \
  -o "2021-03-13 00:00:00" \
  -n "2021-03-16 00:00:00" \
  -s "/opt/splunk" \
  --restart_splunk \
  --check_integrity
```

### Restore Archive from S3

```bash
# Restore from AWS S3
python3 restore-archive-for-splunk.py \
  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" \
  --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/" \
  --index="archive_wineventlog" \
  --oldest_time="2021-03-13 00:00:00" \
  --newest_time="2021-03-16 00:00:00" \
  --splunk_home="/opt/splunk" \
  --s3_default_bucket="s3-frozen-test-bucket" \
  --restart_splunk

# Restore from custom S3 endpoint (e.g., LocalStack)
python3 restore-archive-for-splunk.py \
  --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/" \
  --thaweddb="/opt/splunk/var/lib/splunk/archive_wineventlog/thaweddb/" \
  --index="archive_wineventlog" \
  --oldest_time="2021-03-13 00:00:00" \
  --newest_time="2021-03-16 00:00:00" \
  --splunk_home="/opt/splunk" \
  --s3_path="http://localhost:4566" \
  --s3_default_bucket="s3-frozen-test-bucket" \
  --restart_splunk
```

### Discover Date Range

Find the oldest and newest dates available in your archive:

```bash
# Local environment
python3 restore-archive-for-splunk.py --frozendb="/opt/splunk/var/lib/splunk/wineventlog/frozendb/"

# S3 repository
python3 restore-archive-for-splunk.py \
  --frozendb="/tmp/s3_archives/" \
  --index="wineventlog" \
  --s3_default_bucket="s3-frozen-test-bucket"

# Custom S3 repository
python3 restore-archive-for-splunk.py \
  --frozendb="/tmp/s3_archives/" \
  --index="wineventlog" \
  --s3_path="http://localhost:4566" \
  --s3_default_bucket="s3-frozen-test-bucket"
```

## 🔧 Command Line Arguments

### Required Arguments
- `-f, --frozendb`: Path to frozendb directory containing frozen buckets

### Optional Arguments
- `-t, --thaweddb`: Path where frozen buckets are moved to rebuild
- `-i, --index`: Index name where buckets are rebuilt
- `-o, --oldest_time`: Start date for logs to restore (format: "YYYY-MM-DD HH:MM:SS")
- `-n, --newest_time`: End date for logs to restore (format: "YYYY-MM-DD HH:MM:SS")
- `-s, --splunk_home`: Splunk home directory path
- `--s3_path`: S3 endpoint URL (e.g., http://localhost:4566 for LocalStack)
- `--s3_default_bucket`: S3 bucket name for frozen buckets
- `--list-buckets`: List available buckets with detailed information
- `--restart_splunk`: Restart Splunk after rebuilding (recommended)
- `--check_integrity`: Verify bucket integrity before rebuilding
- `--version`: Show version information
- `-h, --help`: Show help message

## 📊 Logging

The script provides comprehensive logging:

- **Console Output**: User-facing messages and critical errors
- **Log File**: Detailed logging saved to `restore_archive.log`
- **Splunk Logs**: Additional logs saved to `splunk_home/var/log/splunk/` or local `logs/` directory

Log levels include:
- **INFO**: General information and progress updates
- **WARNING**: Non-critical issues (e.g., skipped buckets)
- **ERROR**: Critical errors that may affect operation

## 🧪 Testing

The project includes a comprehensive test suite with 100% pass rate:

```bash
cd test/

# Run all tests
python3 run_tests.py --all

# Run only unit tests
python3 run_tests.py --unit-tests

# Create test data
python3 run_tests.py --create-data
```

### Test Coverage
- Bucket parsing and validation
- Date handling and conversion
- Error handling scenarios
- Edge cases and performance
- Integration testing

## 🔒 Security Features

- **No Shell Injection**: All subprocess calls use secure list arguments
- **Input Validation**: Comprehensive validation of paths, dates, and dependencies
- **Error Handling**: Graceful handling of all error conditions
- **Path Security**: Proper path handling prevents directory traversal

## 🚨 Error Handling

The script provides clear error messages for common issues:

- **Path Validation**: Checks for existence of required paths
- **Dependency Checks**: Validates Splunk binary and AWS CLI availability
- **Date Format**: Validates date format and range
- **S3 Operations**: Handles S3 connection and permission errors
- **Integrity Checks**: Reports bucket integrity issues

## 📈 Performance Improvements

- **Progress Indicators**: Shows current operation progress
- **Efficient Processing**: Optimized bucket scanning and processing
- **Memory Management**: Proper resource cleanup
- **Parallel Operations**: Concurrent processing where safe

## 🔄 Backward Compatibility

All existing command-line usage patterns are preserved. The script maintains full compatibility with previous versions while adding new features and improvements.

## 📝 Examples

### Quick Start
```bash
# List what's available
python3 restore-archive-for-splunk.py --list-buckets --frozendb="/path/to/frozendb/"

# Restore specific date range
python3 restore-archive-for-splunk.py \
  -f "/path/to/frozendb/" \
  -t "/path/to/thaweddb/" \
  -i "my_index" \
  -o "2023-01-01 00:00:00" \
  -n "2023-01-31 23:59:59" \
  -s "/opt/splunk" \
  --check_integrity \
  --restart_splunk
```

### Production Usage
```bash
# Full production restore with all safety checks
python3 restore-archive-for-splunk.py \
  --frozendb="/opt/splunk/var/lib/splunk/production/frozendb/" \
  --thaweddb="/opt/splunk/var/lib/splunk/restored/thaweddb/" \
  --index="production_restored" \
  --oldest_time="2023-06-01 00:00:00" \
  --newest_time="2023-06-30 23:59:59" \
  --splunk_home="/opt/splunk" \
  --check_integrity \
  --restart_splunk
```


## 🆘 Support

For issues or questions:
1. Check the log files for detailed error information
2. Run with `--help` to see all available options
3. Use `--list-buckets` to verify your data is accessible
4. Ensure all dependencies (Splunk, AWS CLI) are properly installed and configured