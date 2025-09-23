# Splunk Bucket Parsing Test Suite

This directory contains a comprehensive test suite for the Splunk archive restoration script, specifically focusing on bucket parsing and validation logic without executing actual Splunk commands.

## Overview

The test suite includes:
- **Unit tests** for bucket parsing and validation functions
- **Integration tests** with realistic test data
- **Test data generator** for creating sample Splunk bucket structures
- **Test runner** for easy execution of all tests

## Files

### Test Files
- `test_bucket_parsing.py` - Main unit test file with comprehensive test cases
- `create_test_data.py` - Test data generator for creating sample bucket structures
- `run_tests.py` - Test runner script for executing all tests
- `README.md` - This documentation file

### Main Script
- `../restore-archive-for-splunk.py` - The main script being tested (with improved error handling)

## Quick Start

All test operations are performed from this `test/` directory:

### Run All Tests
```bash
python3 run_tests.py --all
```

### Run Only Unit Tests
```bash
python3 run_tests.py --unit-tests
```

### Create Test Data Only
```bash
python3 run_tests.py --create-data
```

### Run Integration Test
```bash
python3 run_tests.py --integration-test
```

## Detailed Usage

### 1. Unit Tests (`test_bucket_parsing.py`)

The unit tests cover:

#### TestSplunkBucketParsing Class
- **Valid bucket formats**: Tests finding buckets with correct naming conventions
- **Invalid bucket formats**: Tests handling of malformed bucket names
- **Out-of-range buckets**: Tests filtering of buckets outside time ranges
- **Nonexistent directories**: Tests error handling for missing paths
- **Empty directories**: Tests handling of empty source directories
- **Date parsing**: Tests valid and invalid date format handling
- **Edge cases**: Tests various edge cases in bucket name parsing

#### TestSplunkBucketIntegration Class
- **Comprehensive processing**: Tests mixed valid/invalid data scenarios
- **Performance testing**: Tests with large numbers of buckets (1000+)
- **Real-world scenarios**: Tests realistic bucket processing workflows

#### Running Unit Tests
```bash
# Run with default verbosity
python3 test_bucket_parsing.py

# Run with verbose output
python3 test_bucket_parsing.py -v
```

### 2. Test Data Generator (`create_test_data.py`)

Creates realistic Splunk bucket directory structures for testing.

#### Features
- **Valid buckets**: Creates properly formatted bucket directories
- **Invalid buckets**: Creates malformed bucket names for error testing
- **Out-of-range buckets**: Creates buckets outside test time ranges
- **Realistic structure**: Creates proper Splunk bucket directory layouts
- **Sample data**: Includes sample log files and metadata

#### Usage
```bash
# Create default test data (20 valid, 10 invalid, 5 out-of-range)
python3 create_test_data.py

# Create custom test data
python3 create_test_data.py -o ./my_test_data --valid 50 --invalid 20 --out-of-range 10

# Clean existing directory and create new data
python3 create_test_data.py --clean -o ./test_buckets
```

#### Command Line Options
- `-o, --output`: Output directory (default: ./test_buckets)
- `--valid`: Number of valid buckets to create (default: 20)
- `--invalid`: Number of invalid buckets to create (default: 10)
- `--out-of-range`: Number of out-of-range buckets to create (default: 5)
- `--clean`: Clean output directory before creating test data

### 3. Test Runner (`run_tests.py`)

Provides an easy way to run all tests and manage test data.

#### Usage
```bash
# Run all tests (unit tests, create data, integration test)
python3 run_tests.py --all

# Run only unit tests
python3 run_tests.py --unit-tests

# Create test data only
python3 run_tests.py --create-data

# Run integration test
python3 run_tests.py --integration-test

# Run with verbose output
python3 run_tests.py --all --verbose

# Clean up test data after running
python3 run_tests.py --all --cleanup
```

#### Command Line Options
- `--unit-tests`: Run unit tests
- `--create-data`: Create test data
- `--integration-test`: Run integration test
- `--all`: Run all tests
- `--verbose, -v`: Run tests in verbose mode
- `--test-data-dir`: Directory containing test data (for integration test)
- `--cleanup`: Clean up test data after running tests

## Test Scenarios

### Valid Bucket Formats
The tests expect bucket names in the format:
```
index_epoch1_epoch2_randomid
```
Example: `wineventlog_1609459200_1609459200_1234567890`

### Invalid Bucket Formats Tested
- No underscores: `invalid_bucket`
- Only 2 parts: `wineventlog_1609459200`
- Only 1 part: `wineventlog`
- Only 3 parts: `wineventlog_1609459200_1609459200` (missing randomid)
- Invalid epoch format: `wineventlog_invalid_epoch_1234567890`
- Empty parts: `wineventlog_1609459200_1609459200_`
- Too many parts: `wineventlog_1609459200_1609459200_1234567890_extra`

### Time Range Testing
- **Valid range**: 2021-01-01 to 2022-01-01 (epoch: 1609459200 to 1640995200)
- **Too old**: Before 2021-01-01
- **Too new**: After 2022-01-01

## Expected Test Results

### Unit Tests
- **Tests run**: 11 test cases
- **Success rate**: 100% with proper error handling
- **Coverage**: All major code paths and error conditions

### Integration Tests
- **Valid buckets found**: 20-25 buckets (some edge cases are actually valid)
- **Invalid buckets skipped**: Logged with warnings
- **Out-of-range buckets skipped**: Filtered out correctly

## Error Handling Tests

The test suite specifically tests the improved error handling that fixes "Index out of range" errors:

1. **Bucket name parsing**: Tests handling of malformed bucket names
2. **Regex matching**: Tests handling of unexpected integrity check output
3. **Directory access**: Tests handling of missing or inaccessible directories
4. **Date parsing**: Tests handling of invalid date formats
5. **Edge cases**: Tests various edge cases and boundary conditions

## Performance Testing

The test suite includes performance tests with:
- **Large datasets**: Tests with 1000+ buckets
- **Timing validation**: Ensures processing completes in reasonable time (< 5 seconds)
- **Memory usage**: Monitors memory consumption during processing

## Test Results Summary

When running the full test suite, you should see:

```
==================================================
TEST SUMMARY
==================================================
Tests run: 11
Failures: 0
Errors: 0
Success rate: 100.0%
==================================================
✓ ALL TESTS PASSED!
==================================================
```

## Continuous Integration

The test suite is designed to be CI-friendly:
- **No external dependencies**: Uses only standard Python libraries
- **Deterministic results**: Tests produce consistent results
- **Clean environment**: Tests clean up after themselves
- **Exit codes**: Proper exit codes for CI systems

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're running tests from the `test/` directory
2. **Permission errors**: Ensure write permissions for test data creation
3. **Path issues**: The tests automatically handle relative paths to the main script

### Debug Mode

Run tests with verbose output to see detailed information:
```bash
python3 run_tests.py --all --verbose
```

### Manual Testing

You can manually test specific scenarios by:
1. Creating test data: `python3 create_test_data.py`
2. Examining the created structure
3. Running the main script on the test data
4. Verifying the results

## Contributing

When adding new tests:
1. Follow the existing test structure
2. Add comprehensive docstrings
3. Include both positive and negative test cases
4. Test edge cases and error conditions
5. Update this documentation

## Dependencies

The test suite requires only standard Python libraries:
- `unittest` - For unit testing framework
- `tempfile` - For temporary directory creation
- `shutil` - For file operations
- `os` - For operating system interface
- `sys` - For system-specific parameters
- `subprocess` - For running external commands
- `argparse` - For command line argument parsing
- `time` - For time-related operations
- `datetime` - For date/time handling
- `random` - For generating test data
- `importlib.util` - For dynamic module loading

No external dependencies are required.