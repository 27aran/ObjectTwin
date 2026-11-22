import objecttwin
from objecttwin.__main__ import main


def test_version_is_set() -> None:
    assert objecttwin.__version__


def test_main_is_callable() -> None:
    assert callable(main)
