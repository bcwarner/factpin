# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

"""``python -m factpin`` -- helpers for getting factpin.sty into a LaTeX project."""

from __future__ import annotations

import argparse
import sys

from . import __version__, install_sty, sty_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="factpin", description=__doc__)
    parser.add_argument("--version", action="version", version=f"factpin {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser(
        "install-sty",
        help="print factpin.sty (to paste into Overleaf), or copy it into DESTINATION",
        description=(
            "With no DESTINATION, print factpin.sty to stdout so it can be pasted into a "
            "new file named factpin.sty in an Overleaf project. With a DESTINATION "
            "directory or file path, copy it there and print the new path."
        ),
    )
    install.add_argument("destination", nargs="?", default=None)

    sub.add_parser("sty-path", help="print the path to the bundled factpin.sty")

    args = parser.parse_args(argv)

    if args.command == "install-sty":
        if args.destination is None:
            sys.stdout.write(sty_path().read_text(encoding="utf-8"))
        else:
            print(install_sty(args.destination))
    else:
        print(sty_path())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
