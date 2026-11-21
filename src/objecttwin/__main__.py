"""Entry point: ``python -m objecttwin`` or the ``objecttwin`` executable."""

from __future__ import annotations

from objecttwin import __version__


def main() -> int:
    # Placeholder until the GUI exists (step 4).
    print(f"ObjectTwin {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
