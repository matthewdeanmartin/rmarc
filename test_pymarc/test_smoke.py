"""Smoke tests for rmarc — prove the Rust/Python boundary works."""

import unittest

import rmarc
from rmarc import version


class TestImport(unittest.TestCase):
    def test_import(self) -> None:
        self.assertIsNotNone(rmarc)

    def test_package_version_attr(self) -> None:
        self.assertTrue(hasattr(rmarc, "__version__"))
        self.assertIsInstance(rmarc.__version__, str)
        self.assertGreater(len(rmarc.__version__), 0)


class TestVersionFunction(unittest.TestCase):
    def test_returns_string(self) -> None:
        v = version()
        self.assertIsInstance(v, str)

    def test_non_empty(self) -> None:
        self.assertGreater(len(version()), 0)

    def test_matches_package_version(self) -> None:
        self.assertEqual(rmarc.__version__, version())


if __name__ == "__main__":
    unittest.main()
