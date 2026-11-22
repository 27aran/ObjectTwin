"""Entry point: ``python -m objecttwin`` or ``ObjectTwin.exe``.

* no arguments   -> start the GUI
* ``--self-test`` -> run the installation self-test (see :mod:`objecttwin.selftest`)
"""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        from objecttwin.gui.app import setup_logging
        from objecttwin.selftest import run_self_test

        setup_logging()
        return run_self_test()

    from objecttwin.gui import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
