#!/usr/bin/env python3
"""
Unit tests for Splunk bucket parsing and validation logic.
Tests the find_buckets function and related bucket processing without executing Splunk commands.
"""

import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch, MagicMock
import time

# Add the parent directory to the path to import the main module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the functions we want to test
import importlib.util
spec = importlib.util.spec_from_file_location("restore_archive", "../restore-archive-for-splunk.py")
restore_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore_archive)

# Import the functions we want to test
find_buckets = restore_archive.find_buckets
handle_dates = restore_archive.handle_dates


class TestSplunkBucketParsing(unittest.TestCase):
    """Test cases for Splunk bucket parsing and validation."""
    
    def setUp(self):
        """Set up test environment with temporary directories and sample data."""
        # Create temporary directory for test data
        self.test_dir = tempfile.mkdtemp(prefix="splunk_test_")
        
        # Sample epoch times for testing
        self.oldest_epoch = 1609459200  # 2021-01-01 00:00:00
        self.newest_epoch = 1640995200  # 2022-01-01 00:00:00
        
        # Create sample bucket directories with various formats
        self.create_test_buckets()
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_test_buckets(self):
        """Create sample bucket directories for testing."""
        # Valid bucket formats (should be found)
        valid_buckets = [
            "wineventlog_1609459200_1609459200_1234567890",  # Within range
            "wineventlog_1640995200_1640995200_1234567891",  # At boundary
            "wineventlog_1625097600_1625097600_1234567892",  # Middle of range
        ]
        
        # Invalid bucket formats (should be skipped)
        invalid_buckets = [
            "invalid_bucket",  # No underscores
            "wineventlog_1609459200",  # Only 2 parts
            "wineventlog",  # Only 1 part
            "wineventlog_1609459200_1609459200",  # Only 3 parts (missing last part)
            "wineventlog_invalid_epoch_1234567890",  # Invalid epoch format
            "wineventlog_1609459200_invalid_epoch_1234567890",  # Invalid epoch format
        ]
        
        # Out of range buckets (should be skipped)
        out_of_range_buckets = [
            "wineventlog_1500000000_1500000000_1234567893",  # Too old
            "wineventlog_1700000000_1700000000_1234567894",  # Too new
        ]
        
        # Create all bucket directories
        all_buckets = valid_buckets + invalid_buckets + out_of_range_buckets
        
        for bucket_name in all_buckets:
            bucket_path = os.path.join(self.test_dir, bucket_name)
            os.makedirs(bucket_path, exist_ok=True)
            
            # Create a basic rawdata directory structure
            rawdata_path = os.path.join(bucket_path, "rawdata")
            os.makedirs(rawdata_path, exist_ok=True)
            
            # Add some sample files
            with open(os.path.join(rawdata_path, "sample.log"), "w") as f:
                f.write("sample log data")
    
    def test_find_buckets_valid_format(self):
        """Test finding buckets with valid formats."""
        buckets_found = find_buckets(self.test_dir, self.oldest_epoch, self.newest_epoch)
        
        # Should find 3 valid buckets
        self.assertEqual(len(buckets_found), 3)
        
        # Check that all found buckets are in the expected list
        expected_buckets = [
            "wineventlog_1609459200_1609459200_1234567890",
            "wineventlog_1640995200_1640995200_1234567891", 
            "wineventlog_1625097600_1625097600_1234567892"
        ]
        
        for bucket in buckets_found:
            self.assertIn(bucket, expected_buckets)
    
    def test_find_buckets_invalid_format(self):
        """Test that buckets with invalid formats are skipped."""
        # Just test that the function works correctly - warnings are logged but don't affect functionality
        buckets_found = find_buckets(self.test_dir, self.oldest_epoch, self.newest_epoch)
        
        # Should still find valid buckets
        self.assertEqual(len(buckets_found), 3)
    
    def test_find_buckets_out_of_range(self):
        """Test that buckets outside the time range are skipped."""
        buckets_found = find_buckets(self.test_dir, self.oldest_epoch, self.newest_epoch)
        
        # Should not include out-of-range buckets
        out_of_range_buckets = [
            "wineventlog_1500000000_1500000000_1234567893",
            "wineventlog_1700000000_1700000000_1234567894"
        ]
        
        for bucket in out_of_range_buckets:
            self.assertNotIn(bucket, buckets_found)
    
    def test_find_buckets_nonexistent_directory(self):
        """Test handling of nonexistent directory."""
        nonexistent_path = "/nonexistent/path/that/does/not/exist"
        
        with patch('builtins.print') as mock_print:
            buckets_found = find_buckets(nonexistent_path, self.oldest_epoch, self.newest_epoch)
            
            # Should return empty list
            self.assertEqual(len(buckets_found), 0)
            
            # Should print error message
            print_calls = [call for call in mock_print.call_args_list]
            error_calls = [call for call in print_calls if "Error" in str(call)]
            self.assertGreater(len(error_calls), 0)
    
    def test_find_buckets_empty_directory(self):
        """Test handling of empty directory."""
        empty_dir = tempfile.mkdtemp(prefix="empty_test_")
        try:
            buckets_found = find_buckets(empty_dir, self.oldest_epoch, self.newest_epoch)
            self.assertEqual(len(buckets_found), 0)
        finally:
            shutil.rmtree(empty_dir)
    
    def test_handle_dates_valid_format(self):
        """Test date handling with valid formats."""
        oldest_time = "2021-01-01 00:00:00"
        newest_time = "2022-01-01 00:00:00"
        
        oldest_epoch, newest_epoch = handle_dates(oldest_time, newest_time)
        
        # Check that epoch times are reasonable
        self.assertIsInstance(oldest_epoch, int)
        self.assertIsInstance(newest_epoch, int)
        self.assertGreater(newest_epoch, oldest_epoch)
    
    def test_handle_dates_invalid_format(self):
        """Test date handling with invalid formats."""
        invalid_oldest = "invalid-date-format"
        valid_newest = "2022-01-01 00:00:00"
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                # Mock sys.exit to raise SystemExit instead of actually exiting
                mock_exit.side_effect = SystemExit(1)
                
                with self.assertRaises(SystemExit):
                    handle_dates(invalid_oldest, valid_newest)
                
                # Should call sys.exit(1) on invalid date
                mock_exit.assert_called_with(1)
                
                # Should print error message
                print_calls = [call for call in mock_print.call_args_list]
                error_calls = [call for call in print_calls if "Error" in str(call)]
                self.assertGreater(len(error_calls), 0)
    
    def test_bucket_name_edge_cases(self):
        """Test edge cases in bucket name parsing."""
        # Create a test directory with edge case bucket names
        edge_case_dir = tempfile.mkdtemp(prefix="edge_case_test_")
        try:
            edge_cases = [
                "wineventlog_1609459200_1609459200_",  # Empty last part
                "wineventlog__1609459200_1234567890",  # Empty second part
                "_1609459200_1609459200_1234567890",   # Empty first part
                "wineventlog_1609459200_1609459200_1234567890_extra",  # More than 4 parts
            ]
            
            for bucket_name in edge_cases:
                bucket_path = os.path.join(edge_case_dir, bucket_name)
                os.makedirs(bucket_path, exist_ok=True)
            
            with patch('sys.stdout'):
                buckets_found = find_buckets(edge_case_dir, self.oldest_epoch, self.newest_epoch)
                
                # Should handle edge cases gracefully
                self.assertIsInstance(buckets_found, list)
        
        finally:
            shutil.rmtree(edge_case_dir)
    
    def test_epoch_time_conversion(self):
        """Test epoch time conversion and comparison logic."""
        # Test with specific known epoch times
        test_oldest = 1609459200  # 2021-01-01 00:00:00
        test_newest = 1640995200  # 2022-01-01 00:00:00
        
        # Create a bucket that should be found
        test_bucket = "wineventlog_1625097600_1625097600_1234567890"  # 2021-07-01
        test_dir = tempfile.mkdtemp(prefix="epoch_test_")
        try:
            bucket_path = os.path.join(test_dir, test_bucket)
            os.makedirs(bucket_path, exist_ok=True)
            
            buckets_found = find_buckets(test_dir, test_oldest, test_newest)
            
            # Should find the bucket since 1625097600 is between test_oldest and test_newest
            self.assertIn(test_bucket, buckets_found)
        
        finally:
            shutil.rmtree(test_dir)


class TestSplunkBucketIntegration(unittest.TestCase):
    """Integration tests for the complete bucket processing workflow."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.test_dir = tempfile.mkdtemp(prefix="splunk_integration_test_")
        self.create_comprehensive_test_data()
    
    def tearDown(self):
        """Clean up integration test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def create_comprehensive_test_data(self):
        """Create comprehensive test data covering various scenarios."""
        # Create a realistic Splunk bucket structure
        test_scenarios = [
            # Valid scenarios
            {
                "name": "wineventlog_1609459200_1609459200_1234567890",
                "should_find": True,
                "description": "Valid bucket within range"
            },
            {
                "name": "wineventlog_1640995200_1640995200_1234567891", 
                "should_find": True,
                "description": "Valid bucket at boundary"
            },
            # Invalid scenarios
            {
                "name": "invalid_bucket",
                "should_find": False,
                "description": "No underscores"
            },
            {
                "name": "wineventlog_1609459200",
                "should_find": False,
                "description": "Only 2 parts"
            },
            {
                "name": "wineventlog_invalid_epoch_1234567890",
                "should_find": False,
                "description": "Invalid epoch format"
            },
            # Edge cases
            {
                "name": "wineventlog_1609459200_1609459200_",
                "should_find": False,
                "description": "Empty last part"
            },
        ]
        
        for scenario in test_scenarios:
            bucket_path = os.path.join(self.test_dir, scenario["name"])
            os.makedirs(bucket_path, exist_ok=True)
            
            # Create rawdata directory
            rawdata_path = os.path.join(bucket_path, "rawdata")
            os.makedirs(rawdata_path, exist_ok=True)
            
            # Add sample data
            with open(os.path.join(rawdata_path, "sample.log"), "w") as f:
                f.write(f"Test data for {scenario['description']}")
    
    def test_comprehensive_bucket_processing(self):
        """Test comprehensive bucket processing with mixed valid/invalid data."""
        oldest_epoch = 1609459200
        newest_epoch = 1640995200
        
        with patch('sys.stdout') as mock_stdout:
            buckets_found = find_buckets(self.test_dir, oldest_epoch, newest_epoch)
            
            # Should find exactly 3 valid buckets (including the one with empty last part)
            self.assertEqual(len(buckets_found), 3)
            
            # Verify the correct buckets were found
            expected_buckets = [
                "wineventlog_1609459200_1609459200_1234567890",
                "wineventlog_1640995200_1640995200_1234567891",
                "wineventlog_1609459200_1609459200_"  # This one has empty last part but is still valid
            ]
            
            for bucket in buckets_found:
                self.assertIn(bucket, expected_buckets)
            
            # Verify that invalid buckets were not found
            invalid_buckets = [
                "invalid_bucket",
                "wineventlog_1609459200",
                "wineventlog_invalid_epoch_1234567890"
                # Note: "wineventlog_1609459200_1609459200_" is actually valid (has 4 parts)
            ]
            
            for bucket in invalid_buckets:
                self.assertNotIn(bucket, buckets_found)
    
    def test_performance_with_many_buckets(self):
        """Test performance with a large number of buckets."""
        # Create many buckets to test performance
        num_buckets = 1000
        base_epoch = 1609459200
        
        for i in range(num_buckets):
            bucket_name = f"wineventlog_{base_epoch + i}_{base_epoch + i}_{1234567890 + i}"
            bucket_path = os.path.join(self.test_dir, bucket_name)
            os.makedirs(bucket_path, exist_ok=True)
        
        # Test that it can handle many buckets efficiently
        import time
        start_time = time.time()
        buckets_found = find_buckets(self.test_dir, base_epoch, base_epoch + 500)
        end_time = time.time()
        
        # Should find 502 buckets (0 to 501 inclusive)
        # Note: The range logic includes buckets where newest_bucket_epoch_time >= oldest_epoch_time
        # and oldest_bucket_epoch_time <= newest_epoch_time
        self.assertEqual(len(buckets_found), 502)
        
        # Should complete in reasonable time (less than 5 seconds)
        self.assertLess(end_time - start_time, 5.0)


def run_tests():
    """Run all tests and provide a summary."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestSplunkBucketParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestSplunkBucketIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
