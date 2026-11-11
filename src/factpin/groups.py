# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

"""Groups: the unit + formatting profile shared by a set of constants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

__all__ = ["Group", "BUILTIN_FORMATS"]

#: Formats shipped in factpin.sty, mapped to the number of values they expect.
#: ``None`` means "any number of values".
BUILTIN_FORMATS = {
    "plain": None,
    "list": None,
    "ci": 3,
    "range": 2,
    "pm": 2,
}

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _check_name(name: str, what: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            f"invalid {what} name {name!r}: must start with a letter and contain "
            "only letters, digits and underscores (so it is safe in \\csname and \\label)"
        )
    return name


@dataclass(frozen=True)
class Group:
    """A unit and rounding profile applied to every constant in the group.

    ``unit`` is raw siunitx syntax (e.g. ``r"\\milli\\second"``) and is passed through
    untouched -- factpin takes no opinion on unit systems and pulls in no unit library.
    """

    name: str
    unit: str = ""
    places: Optional[int] = None
    sigfigs: Optional[int] = None
    format: str = "plain"
    siunitx: str = ""

    def __post_init__(self) -> None:
        _check_name(self.name, "group")
        _check_name(self.format, "format")
        if self.places is not None and self.sigfigs is not None:
            raise ValueError(
                f"group {self.name!r}: set places or sigfigs, not both"
            )
        for attr in ("places", "sigfigs"):
            n = getattr(self, attr)
            if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n < 0):
                raise ValueError(f"group {self.name!r}: {attr} must be a non-negative int")

    @property
    def arity(self) -> Optional[int]:
        """How many values this group's format expects, or None for any."""
        return BUILTIN_FORMATS.get(self.format)

    def siunitx_options(self) -> str:
        """Translate the friendly keywords into a siunitx option list."""
        opts = []
        if self.places is not None:
            opts.append(f"round-mode=places,round-precision={self.places}")
        elif self.sigfigs is not None:
            opts.append(f"round-mode=figures,round-precision={self.sigfigs}")
        if self.siunitx:
            # Appended last so an explicit escape hatch always wins.
            opts.append(self.siunitx)
        return ",".join(opts)
