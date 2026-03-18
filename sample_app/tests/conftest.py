"""Shared fixtures for sample_app tests."""

import sys
from pathlib import Path

# Ensure sample_app is importable when running tests from repo root
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
