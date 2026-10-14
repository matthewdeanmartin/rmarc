"""Run the same tiny example against a reference and the reported version."""

import importlib
import importlib.metadata

import pytest


def pytest_report_header():
    return " | ".join(f"{name} {importlib.metadata.version(name)}" for name in ("pymarc", "mrrc"))


@pytest.fixture(params=["pymarc", "mrrc"])
def marc(request):
    return importlib.import_module(request.param)
