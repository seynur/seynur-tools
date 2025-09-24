#!/usr/bin/env python3
"""
Test data generator for Splunk bucket testing.
Creates realistic Splunk bucket directory structures for testing purposes.
"""

import os
import sys
import argparse
import time
from datetime import datetime, timedelta
import random


def create_splunk_bucket_structure(base_path, bucket_name, index_name="wineventlog"):
    """Create a realistic Splunk bucket directory structure.
    
    Args:
        base_path (str): Base directory path
        bucket_name (str): Name of the bucket directory
        index_name (str): Name of the index (default: wineventlog)
    """
    bucket_path = os.path.join(base_path, bucket_name)
    
    # Create main bucket directory
    os.makedirs(bucket_path, exist_ok=True)
    
    # Create rawdata directory
    rawdata_path = os.path.join(bucket_path, "rawdata")
    os.makedirs(rawdata_path, exist_ok=True)
    
    # Create some sample log files
    sample_logs = [
        "host1.log",
        "host2.log", 
        "application.log",
        "system.log"
    ]
    
    for log_file in sample_logs:
        log_path = os.path.join(rawdata_path, log_file)
        with open(log_path, "w") as f:
            # Generate some sample log data
            for _ in range(random.randint(10, 50)):
                timestamp = datetime.now() - timedelta(hours=random.randint(0, 24))
                f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} INFO Sample log entry from {log_file}\n")
    
    # Create db directory structure (simplified)
    db_path = os.path.join(bucket_path, "db")
    os.makedirs(db_path, exist_ok=True)
    
    # Create some metadata files
    metadata_files = [
        "bucketmanifest",
        "rawdata",
        "tsidx"
    ]
    
    for meta_file in metadata_files:
        meta_path = os.path.join(db_path, meta_file)
        with open(meta_path, "w") as f:
            f.write(f"# Metadata for {meta_file}\n")
            f.write(f"# Bucket: {bucket_name}\n")
            f.write(f"# Index: {index_name}\n")
            f.write(f"# Created: {datetime.now().isoformat()}\n")


def generate_valid_bucket_names(count=10, index_name="wineventlog", start_date=None, end_date=None):
    """Generate valid Splunk bucket names.
    
    Args:
        count (int): Number of bucket names to generate
        index_name (str): Name of the index
        start_date (datetime): Start date for bucket generation
        end_date (datetime): End date for bucket generation
    
    Returns:
        list: List of valid bucket names
    """
    if start_date is None:
        start_date = datetime(2021, 1, 1)
    if end_date is None:
        end_date = datetime(2022, 1, 1)
    
    bucket_names = []
    time_range = (end_date - start_date).total_seconds()
    
    for i in range(count):
        # Generate random timestamp within range
        random_seconds = random.randint(0, int(time_range))
        bucket_time = start_date + timedelta(seconds=random_seconds)
        epoch_time = int(bucket_time.timestamp())
        
        # Generate bucket name: index_epoch_epoch_randomid
        bucket_name = f"{index_name}_{epoch_time}_{epoch_time}_{random.randint(1000000000, 9999999999)}"
        bucket_names.append(bucket_name)
    
    return bucket_names


def generate_invalid_bucket_names(count=5):
    """Generate invalid Splunk bucket names for testing error handling.
    
    Args:
        count (int): Number of invalid bucket names to generate
    
    Returns:
        list: List of invalid bucket names
    """
    invalid_patterns = [
        "invalid_bucket",  # No underscores
        "wineventlog_1609459200",  # Only 2 parts
        "wineventlog",  # Only 1 part
        "wineventlog_1609459200_1609459200",  # Only 3 parts
        "wineventlog_invalid_epoch_1234567890",  # Invalid epoch
        "wineventlog_1609459200_invalid_epoch_1234567890",  # Invalid epoch
        "wineventlog_1609459200_1609459200_",  # Empty last part
        "wineventlog__1609459200_1234567890",  # Empty second part
        "_1609459200_1609459200_1234567890",   # Empty first part
        "wineventlog_1609459200_1609459200_1234567890_extra",  # Too many parts
    ]
    
    return invalid_patterns[:count]


def create_test_environment(output_dir, num_valid=20, num_invalid=10, num_out_of_range=5):
    """Create a comprehensive test environment with various bucket types.
    
    Args:
        output_dir (str): Directory to create test data in
        num_valid (int): Number of valid buckets to create
        num_invalid (int): Number of invalid buckets to create
        num_out_of_range (int): Number of out-of-range buckets to create
    """
    print(f"Creating test environment in: {output_dir}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate valid buckets (within test range)
    print(f"Creating {num_valid} valid buckets...")
    valid_buckets = generate_valid_bucket_names(
        count=num_valid,
        start_date=datetime(2021, 1, 1),
        end_date=datetime(2022, 1, 1)
    )
    
    for bucket_name in valid_buckets:
        create_splunk_bucket_structure(output_dir, bucket_name)
    
    # Generate invalid buckets
    print(f"Creating {num_invalid} invalid buckets...")
    invalid_buckets = generate_invalid_bucket_names(num_invalid)
    
    for bucket_name in invalid_buckets:
        create_splunk_bucket_structure(output_dir, bucket_name)
    
    # Generate out-of-range buckets
    print(f"Creating {num_out_of_range} out-of-range buckets...")
    out_of_range_buckets = generate_valid_bucket_names(
        count=num_out_of_range,
        start_date=datetime(2020, 1, 1),  # Too old
        end_date=datetime(2020, 12, 31)
    ) + generate_valid_bucket_names(
        count=num_out_of_range,
        start_date=datetime(2023, 1, 1),  # Too new
        end_date=datetime(2023, 12, 31)
    )
    
    for bucket_name in out_of_range_buckets:
        create_splunk_bucket_structure(output_dir, bucket_name)
    
    # Create a summary file
    summary_path = os.path.join(output_dir, "test_data_summary.txt")
    with open(summary_path, "w") as f:
        f.write("Splunk Test Data Summary\n")
        f.write("=" * 50 + "\n\n")
        f.write("Total buckets created: {}\n".format(num_valid + num_invalid + len(out_of_range_buckets)))
        f.write(f"Valid buckets (should be found): {num_valid}\n")
        f.write(f"Invalid buckets (should be skipped): {num_invalid}\n")
        f.write(f"Out-of-range buckets (should be skipped): {len(out_of_range_buckets)}\n\n")
        
        f.write("Valid buckets:\n")
        for bucket in valid_buckets:
            f.write(f"  - {bucket}\n")
        
        f.write("\nInvalid buckets:\n")
        for bucket in invalid_buckets:
            f.write(f"  - {bucket}\n")
        
        f.write("\nOut-of-range buckets:\n")
        for bucket in out_of_range_buckets:
            f.write(f"  - {bucket}\n")
    
    print(f"Test environment created successfully!")
    print(f"Summary written to: {summary_path}")
    print(f"Valid buckets: {num_valid}")
    print(f"Invalid buckets: {num_invalid}")
    print(f"Out-of-range buckets: {len(out_of_range_buckets)}")


def main():
    """Main function to create test data."""
    parser = argparse.ArgumentParser(description="Create test data for Splunk bucket testing")
    parser.add_argument(
        "-o", "--output", 
        default="./test_buckets", 
        help="Output directory for test data (default: ./test_buckets)"
    )
    parser.add_argument(
        "--valid", 
        type=int, 
        default=20, 
        help="Number of valid buckets to create (default: 20)"
    )
    parser.add_argument(
        "--invalid", 
        type=int, 
        default=10, 
        help="Number of invalid buckets to create (default: 10)"
    )
    parser.add_argument(
        "--out-of-range", 
        type=int, 
        default=5, 
        help="Number of out-of-range buckets to create (default: 5)"
    )
    parser.add_argument(
        "--clean", 
        action="store_true", 
        help="Clean output directory before creating test data"
    )
    
    args = parser.parse_args()
    
    # Clean output directory if requested
    if args.clean and os.path.exists(args.output):
        import shutil
        print(f"Cleaning output directory: {args.output}")
        shutil.rmtree(args.output)
    
    # Create test environment
    create_test_environment(
        output_dir=args.output,
        num_valid=args.valid,
        num_invalid=args.invalid,
        num_out_of_range=args.out_of_range
    )


if __name__ == "__main__":
    main()
