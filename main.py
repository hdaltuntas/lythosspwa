#!/usr/bin/env python3
"""Run Lythos SPWA without installing it.

    python main.py                      opens the interface in a browser
    python main.py run project.spwa     analyses a project file
    python main.py study project.spwa   runs the study a project file defines
    python main.py example              writes a starter project file

This file puts its own directory on the import path, so a fresh clone runs with
nothing installed beyond NumPy, SciPy, Matplotlib and reportlab.
"""

from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REQUIRED = ["numpy", "scipy", "matplotlib", "reportlab"]


def missing_packages() -> list:
    return [name for name in REQUIRED if importlib.util.find_spec(name) is None]


def explain(missing: list) -> None:
    print("Lythos SPWA needs these Python packages, which are not installed:\n",
          file=sys.stderr)
    for name in missing:
        print(f"    {name}", file=sys.stderr)
    print("\nInstall them in a virtual environment:\n", file=sys.stderr)
    print(f"    python -m venv .venv\n    source .venv/bin/activate\n"
          f"    pip install {' '.join(missing)}\n", file=sys.stderr)
    print("Or, on a distribution that manages Python packages itself:\n", file=sys.stderr)
    print(f"    sudo apt install {' '.join('python3-' + n for n in missing)}", file=sys.stderr)


def main() -> int:
    if sys.version_info < (3, 10):
        print(f"Lythos SPWA needs Python 3.10 or later; this is "
              f"{sys.version.split()[0]}.", file=sys.stderr)
        return 1
    gaps = missing_packages()
    if gaps:
        explain(gaps)
        return 1
    from lythosspwa.cli import main as run_cli
    return run_cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
