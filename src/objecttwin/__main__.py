"""Entry point: ``python -m objecttwin`` or the ``objecttwin`` executable (starts the GUI)."""

from __future__ import annotations


def main() -> int:
    from objecttwin.gui import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
