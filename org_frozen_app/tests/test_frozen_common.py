# -*- coding: utf-8 -*-
"""Unit tests for bin/frozen_common.py (exclude tests/ from Splunk app package)."""

from __future__ import print_function

import os
import shutil
import sys
import tempfile
import unittest

BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import frozen_common as common  # noqa: E402


class TestDecode(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(common.decode(b"  hello\n"), "hello")

    def test_none(self):
        self.assertEqual(common.decode(None), "")

    def test_str(self):
        self.assertEqual(common.decode(" x "), "x")


class TestKvFields(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(common.kv_fields(status="ok", n=1), "status=ok n=1")

    def test_quotes_spaces(self):
        out = common.kv_fields(error="no such file")
        self.assertEqual(out, 'error="no such file"')


class TestIndexFromBucketPath(unittest.TestCase):
    def test_colddb(self):
        path = "/data/my_index/colddb/db_1000_900_1"
        self.assertEqual(common.index_from_bucket_path(path), "my_index")

    def test_db(self):
        path = "/opt/splunk/var/lib/splunk/web/db/db_1_0_0"
        self.assertEqual(common.index_from_bucket_path(path), "web")

    def test_frozendb(self):
        path = "/data/sec/frozendb/db_1_0_0"
        self.assertEqual(common.index_from_bucket_path(path), "sec")

    def test_bad_layout(self):
        with self.assertRaises(ValueError):
            common.index_from_bucket_path("/tmp/not_a_bucket")


class TestLocalFileCount(unittest.TestCase):
    def test_counts_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "rawdata"))
            open(os.path.join(tmp, "rawdata", "journal.gz"), "w").close()
            open(os.path.join(tmp, "Hosts.data"), "w").close()
            self.assertEqual(common.local_file_count(tmp), 2)


class TestParseBucketArg(unittest.TestCase):
    def test_missing_arg(self):
        with self.assertRaises(ValueError):
            common.parse_bucket_arg(["coldToFrozenSCP.py"])

    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            index_dir = os.path.join(tmp, "idx1", "colddb", "db_1_0_0")
            os.makedirs(index_dir)
            open(os.path.join(index_dir, "f"), "w").close()
            bucket, index, name = common.parse_bucket_arg(["prog", index_dir])
            self.assertEqual(index, "idx1")
            self.assertEqual(name, "db_1_0_0")
            self.assertTrue(os.path.isdir(bucket))


class TestCollectFrozenArtifacts(unittest.TestCase):
    def _bucket(self, *raw_files):
        tmp = tempfile.mkdtemp()
        rawdata = os.path.join(tmp, "rawdata")
        os.makedirs(rawdata)
        for name in raw_files:
            open(os.path.join(rawdata, name), "w").close()
        self.addCleanup(shutil.rmtree, tmp, True)
        return tmp

    def test_journal_zst_only(self):
        bucket = self._bucket("journal.zst")
        arts = common.collect_frozen_artifacts(bucket)
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0][1], os.path.join("rawdata", "journal.zst"))

    def test_journal_gz_with_l2hash(self):
        bucket = self._bucket("journal.gz", "l2hash")
        arts = common.collect_frozen_artifacts(bucket)
        self.assertEqual(len(arts), 2)
        rels = [a[1] for a in arts]
        self.assertEqual(rels[0], os.path.join("rawdata", "journal.gz"))
        self.assertEqual(rels[1], os.path.join("rawdata", "l2hash"))

    def test_no_journal(self):
        bucket = self._bucket("l2hash")
        with self.assertRaises(ValueError):
            common.collect_frozen_artifacts(bucket)

    def test_multiple_journals(self):
        bucket = self._bucket("journal.gz", "journal.zst")
        with self.assertRaises(ValueError):
            common.collect_frozen_artifacts(bucket)

    def test_no_rawdata(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with self.assertRaises(ValueError):
            common.collect_frozen_artifacts(tmp)


class TestBuildFrozenStagingDir(unittest.TestCase):
    def test_layout(self):
        with tempfile.TemporaryDirectory() as bucket:
            rawdata = os.path.join(bucket, "rawdata")
            os.makedirs(rawdata)
            with open(os.path.join(rawdata, "journal.zst"), "w") as fh:
                fh.write("j")
            with open(os.path.join(rawdata, "l2hash"), "w") as fh:
                fh.write("h")
            arts = common.collect_frozen_artifacts(bucket)
            staging = common.build_frozen_staging_dir(arts)
            try:
                self.assertTrue(
                    os.path.isfile(os.path.join(staging, "rawdata", "journal.zst")))
                self.assertTrue(
                    os.path.isfile(os.path.join(staging, "rawdata", "l2hash")))
                self.assertEqual(common.local_file_count(staging), 2)
                self.assertFalse(os.path.exists(os.path.join(staging, "Hosts.data")))
            finally:
                shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
