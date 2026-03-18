from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent


def fixture_path(name: str) -> Path:
    return TEST_DIR / name
