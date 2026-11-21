import objecttwin
from objecttwin.__main__ import main


def test_version_is_set() -> None:
    assert objecttwin.__version__


def test_main_returns_zero() -> None:
    assert main() == 0
