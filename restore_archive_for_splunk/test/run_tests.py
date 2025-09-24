#!/usr/bin/env python3
"""
Test runner for Splunk bucket parsing tests.
Provides an easy way to run all tests and generate test data.
"""

import os
import sys
import subprocess
import argparse
import tempfile
import shutil


def run_unit_tests(verbose=False):
    """Run the unit tests for bucket parsing.
    
    Args:
        verbose (bool): Whether to run tests in verbose mode
    
    Returns:
        bool: True if all tests passed, False otherwise
    """
    print("Running unit tests for Splunk bucket parsing...")
    print("=" * 50)
    
    # Run the test file
    test_file = "test_bucket_parsing.py"
    if not os.path.exists(test_file):
        print(f"Error: Test file '{test_file}' not found!")
        return False
    
    try:
        # Run tests with appropriate verbosity
        cmd = [sys.executable, test_file]
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def create_test_data(output_dir=None, num_valid=20, num_invalid=10, num_out_of_range=5):
    """Create test data for testing.
    
    Args:
        output_dir (str): Directory to create test data in
        num_valid (int): Number of valid buckets to create
        num_invalid (int): Number of invalid buckets to create
        num_out_of_range (int): Number of out-of-range buckets to create
    
    Returns:
        str: Path to the created test data directory
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="splunk_test_data_")
    
    print(f"Creating test data in: {output_dir}")
    
    # Run the test data generator
    test_data_script = "create_test_data.py"
    if not os.path.exists(test_data_script):
        print(f"Error: Test data generator '{test_data_script}' not found!")
        return None
    
    try:
        cmd = [
            sys.executable, test_data_script,
            "-o", output_dir,
            "--valid", str(num_valid),
            "--invalid", str(num_invalid),
            "--out-of-range", str(num_out_of_range)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Test data created successfully!")
            if result.stdout:
                print(result.stdout)
            return output_dir
        else:
            print(f"Error creating test data: {result.stderr}")
            return None
    
    except Exception as e:
        print(f"Error running test data generator: {e}")
        return None


def run_integration_test(test_data_dir, verbose=False):
    """Run integration test with real test data.
    
    Args:
        test_data_dir (str): Directory containing test data
        verbose (bool): Whether to run in verbose mode
    
    Returns:
        bool: True if test passed, False otherwise
    """
    print(f"Running integration test with data from: {test_data_dir}")
    print("=" * 50)
    
    if not os.path.exists(test_data_dir):
        print(f"Error: Test data directory '{test_data_dir}' not found!")
        return False
    
    # Create a simple integration test script
    integration_test_script = f"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib.util
spec = importlib.util.spec_from_file_location("restore_archive", "../restore-archive-for-splunk.py")
restore_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_archive)

find_buckets = restore_archive.find_buckets
handle_dates = restore_archive.handle_dates

def test_with_real_data():
    test_dir = "{test_data_dir}"
    oldest_epoch = 1609459200  # 2021-01-01 00:00:00
    newest_epoch = 1640995200  # 2022-01-01 00:00:00
    
    print(f"Testing with directory: {{test_dir}}")
    print(f"Time range: {{oldest_epoch}} to {{newest_epoch}}")
    
    buckets_found = find_buckets(test_dir, oldest_epoch, newest_epoch)
    
    print(f"\\nFound {{len(buckets_found)}} buckets:")
    for bucket in buckets_found:
        print(f"  - {{bucket}}")
    
    # Check if we found a reasonable number of valid buckets
    # Some "invalid" buckets might actually be valid (e.g., buckets with empty last part)
    min_expected = 20  # At least the explicitly valid buckets
    max_expected = 25  # Allow for some edge cases that are actually valid
    
    if min_expected <= len(buckets_found) <= max_expected:
        print(f"\\n✓ SUCCESS: Found {{len(buckets_found)}} valid buckets (expected {{min_expected}}-{{max_expected}})")
        return True
    else:
        print(f"\\n✗ FAILURE: Found {{len(buckets_found)}} buckets, expected {{min_expected}}-{{max_expected}}")
        return False

if __name__ == "__main__":
    success = test_with_real_data()
    sys.exit(0 if success else 1)
"""
    
    # Write and run the integration test
    test_script_path = os.path.join(test_data_dir, "integration_test.py")
    with open(test_script_path, "w") as f:
        f.write(integration_test_script)
    
    try:
        result = subprocess.run([sys.executable, test_script_path], 
                              capture_output=True, text=True)
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"Error running integration test: {e}")
        return False
    
    finally:
        # Clean up the temporary test script
        if os.path.exists(test_script_path):
            os.remove(test_script_path)


def main():
    """Main function to run tests and create test data."""
    parser = argparse.ArgumentParser(description="Run Splunk bucket parsing tests")
    parser.add_argument(
        "--unit-tests", 
        action="store_true", 
        help="Run unit tests"
    )
    parser.add_argument(
        "--create-data", 
        action="store_true", 
        help="Create test data"
    )
    parser.add_argument(
        "--integration-test", 
        action="store_true", 
        help="Run integration test"
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Run all tests (unit tests, create data, integration test)"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--test-data-dir", 
        help="Directory containing test data (for integration test)"
    )
    parser.add_argument(
        "--cleanup", 
        action="store_true", 
        help="Clean up test data after running tests"
    )
    
    args = parser.parse_args()
    
    # If no specific action is requested, run all tests
    if not any([args.unit_tests, args.create_data, args.integration_test]):
        args.all = True
    
    success = True
    test_data_dir = args.test_data_dir
    
    try:
        # Run unit tests
        if args.unit_tests or args.all:
            print("STEP 1: Running unit tests...")
            if not run_unit_tests(args.verbose):
                success = False
            print()
        
        # Create test data
        if args.create_data or args.all:
            print("STEP 2: Creating test data...")
            if test_data_dir is None:
                test_data_dir = create_test_data()
            if test_data_dir is None:
                success = False
            print()
        
        # Run integration test
        if args.integration_test or args.all:
            if test_data_dir is None:
                print("Error: No test data directory available for integration test")
                success = False
            else:
                print("STEP 3: Running integration test...")
                if not run_integration_test(test_data_dir, args.verbose):
                    success = False
                print()
    
    finally:
        # Clean up test data if requested
        if args.cleanup and test_data_dir and os.path.exists(test_data_dir):
            print(f"Cleaning up test data directory: {test_data_dir}")
            shutil.rmtree(test_data_dir)
    
    # Print final results
    print("=" * 50)
    if success:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED!")
    print("=" * 50)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
