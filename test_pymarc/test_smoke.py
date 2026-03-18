"""Smoke tests for rmarc Phase 1 — prove the Rust/Python boundary works."""

import unittest

import rmarc
from rmarc import MarcRecord, version


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


class TestMarcRecord(unittest.TestCase):
    def test_instantiation(self) -> None:
        rec = MarcRecord("245")
        self.assertIsNotNone(rec)

    def test_tag_attribute(self) -> None:
        rec = MarcRecord("245")
        self.assertEqual(rec.tag, "245")

    def test_tag_settable(self) -> None:
        rec = MarcRecord("245")
        rec.tag = "100"
        self.assertEqual(rec.tag, "100")

    def test_value_method(self) -> None:
        rec = MarcRecord("245")
        self.assertEqual(rec.value(), "stub")

    def test_different_tags(self) -> None:
        for tag in ("001", "100", "245", "856"):
            with self.subTest(tag=tag):
                rec = MarcRecord(tag)
                self.assertEqual(rec.tag, tag)


if __name__ == "__main__":
    unittest.main()
