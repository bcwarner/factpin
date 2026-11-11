# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

"""Serialisation of Python values into siunitx-readable number strings.

factpin deliberately writes values at *full precision*: rounding and precision are
presentation concerns that belong to siunitx in the manuscript, not to the analysis
code.  Changing a group from three decimal places to two must never require re-running
the analysis.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

__all__ = ["format_value", "format_bool", "is_bool"]

# How a pinned bool is typeset. Fixed for now; expected to become configurable later.
_BOOL_TEXT = {True: r"\texttt{True}", False: r"\texttt{False}"}


def is_bool(value: Any) -> bool:
    """True for Python bools and numpy bools (which are not ``bool`` subclasses)."""
    if isinstance(value, bool):
        return True
    cls = type(value)
    return cls.__module__ == "numpy" and cls.__name__ in ("bool_", "bool")


def format_bool(value: Any) -> str:
    """Return the raw LaTeX a bool is pinned as. Bools are text, not numbers."""
    return _BOOL_TEXT[bool(value)]


def format_value(value: Any) -> str:
    """Return *value* as a string siunitx can parse, losing no precision.

    Accepts ints, floats, ``Decimal`` and anything float-like (numpy scalars).
    Raises ``TypeError`` for unsupported types and ``ValueError`` for NaN/infinity,
    which siunitx would otherwise typeset as silent nonsense.
    """
    if is_bool(value):
        # bool is an int subclass (and numpy's has __float__), so without this check it
        # would silently become 1/0. Bools are pinned as text via format_bool instead.
        raise TypeError("a bool is not a number; Context.add pins it as text")

    if isinstance(value, int):
        return str(value)

    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"cannot pin non-finite value {value!r}")
        # siunitx reads 'e' as the exponent marker; Decimal emits 'E'.
        return str(value).replace("E", "e")

    if isinstance(value, float):
        return _format_float(value)

    if hasattr(value, "__float__"):  # numpy scalars, Fraction, ...
        return _format_float(float(value))

    raise TypeError(
        f"cannot pin value of type {type(value).__name__!r}; "
        "expected int, float, Decimal or a float-like object"
    )


def _format_float(value: float) -> str:
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"cannot pin non-finite value {value!r}")
    # repr() is the shortest string that round-trips exactly in Python 3.
    return repr(value)
