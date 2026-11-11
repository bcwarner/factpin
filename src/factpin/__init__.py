# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

"""factpin -- pin constants computed in analysis code into a LaTeX manuscript.

Python owns the values, LaTeX owns the presentation::

    import factpin

    ctx = factpin.Context("results")
    ctx.add_group("auroc", places=3, format="ci")
    ctx.add("auroc_a_ci", values=[0.5, 0.45, 0.55], group="auroc")
    ctx.write()

The generated ``results.tex`` is ``\\input`` by the manuscript, which then uses
``\\const{auroc_a_ci}`` to typeset the value through siunitx.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Union

from .context import Constant, Context
from .groups import BUILTIN_FORMATS, Group

__version__ = "0.2.0"

__all__ = [
    "Context",
    "Constant",
    "Group",
    "BUILTIN_FORMATS",
    "sty_path",
    "install_sty",
    "__version__",
]


def sty_path() -> Path:
    """Absolute path to the bundled ``factpin.sty``."""
    return Path(__file__).resolve().parent / "tex" / "factpin.sty"


def install_sty(destination: Union[str, "Path"] = ".") -> Path:
    """Copy ``factpin.sty`` next to a manuscript and return the new path.

    Overleaf projects have no access to the local Python environment, so the style file
    has to live in the project itself. Run this against the directory you sync to
    Overleaf (or upload the returned file by hand).
    """
    target = Path(destination)
    if target.is_dir():
        target = target / "factpin.sty"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sty_path(), target)
    return target
