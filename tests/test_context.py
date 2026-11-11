# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

from decimal import Decimal

import pytest

import factpin
from factpin.numbers import format_value


def test_scalar_and_tuple_round_trip():
    ctx = factpin.Context("results")
    ctx.add_group("auroc", places=3, format="ci")
    ctx.add("auroc_a_mean", value=0.5, group="auroc")
    ctx.add("auroc_a_ci", values=[0.5, 0.45, 0.55], group="auroc")

    assert ctx.constants[0].render() == "\\declconst{auroc_a_mean}{0.5}{auroc}"
    assert ctx.constants[1].render() == "\\declconst{auroc_a_ci}{0.5,0.45,0.55}{auroc}"


def test_group_is_optional_and_carries_no_unit():
    ctx = factpin.Context("results")
    ctx.add("n_patients", value=1234)
    assert ctx.constants[0].render() == "\\declconst{n_patients}{1234}{}"
    assert ctx.groups == []


def test_values_are_written_at_full_precision():
    # Rounding is siunitx's job; Python must not quietly lose bits.
    ctx = factpin.Context("results")
    ctx.add("x", value=0.1 + 0.2)
    written = ctx.constants[0].values[0]
    assert float(written) == 0.1 + 0.2
    assert written == "0.30000000000000004"


@pytest.mark.parametrize(
    "value,expected",
    [
        (5, "5"),
        (-3, "-3"),
        (0.5, "0.5"),
        (1e-5, "1e-05"),
        (Decimal("1.500"), "1.500"),
        (Decimal("1E+2"), "1e+2"),
    ],
)
def test_format_value(value, expected):
    assert format_value(value) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_rejected(bad):
    with pytest.raises(ValueError, match="non-finite"):
        format_value(bad)


def test_bool_and_str_rejected_by_format_value():
    with pytest.raises(TypeError):
        format_value(True)
    with pytest.raises(TypeError):
        format_value("0.5")


def test_float_like_objects_accepted():
    class Scalar:
        def __float__(self):
            return 2.5

    assert format_value(Scalar()) == "2.5"


def test_exactly_one_of_value_or_values():
    ctx = factpin.Context("results")
    with pytest.raises(ValueError, match="exactly one"):
        ctx.add("x")
    with pytest.raises(ValueError, match="exactly one"):
        ctx.add("x", value=1, values=[1, 2])
    with pytest.raises(ValueError, match="must not be empty"):
        ctx.add("x", values=[])


@pytest.mark.parametrize("bad", ["1x", "with-dash", "with space", "", "_leading"])
def test_invalid_names_rejected(bad):
    ctx = factpin.Context("results")
    with pytest.raises(ValueError, match="invalid constant name"):
        ctx.add(bad, value=1)


def test_unknown_group_rejected():
    ctx = factpin.Context("results")
    ctx.add_group("auroc", places=3)
    with pytest.raises(ValueError, match="unknown group 'typo'"):
        ctx.add("x", value=1, group="typo")


def test_duplicate_constant_rejected_unless_overwrite():
    ctx = factpin.Context("results")
    ctx.add("x", value=1)
    with pytest.raises(ValueError, match="already pinned"):
        ctx.add("x", value=2)
    ctx.add("x", value=2, overwrite=True)
    assert ctx.constants[0].values == ["2"]
    assert len(ctx) == 1


def test_text_constant_renders_without_a_group():
    ctx = factpin.Context("results")
    ctx.add_text("best_model", r"Logistic regression (\textsc{l1})")
    c = ctx.constants[0]
    assert c.text
    assert c.render() == "\\declconsttext{best_model}{Logistic regression (\\textsc{l1})}"


def test_text_shares_the_namespace_with_numeric_constants():
    ctx = factpin.Context("results")
    ctx.add("x", value=1)
    with pytest.raises(ValueError, match="already pinned"):
        ctx.add_text("x", "one")
    ctx.add_text("x", "one", overwrite=True)
    assert len(ctx) == 1
    assert ctx.constants[0].text


@pytest.mark.parametrize(
    "bad,match",
    [
        ("", "must not be empty"),
        ("   ", "must not be empty"),
        ("two\nlines", "single line"),
        ("95% CI", "unescaped '%'"),
        (r"\textsc{open", "unclosed"),
        ("closed}", "unbalanced"),
    ],
)
def test_text_that_would_corrupt_the_generated_file_is_rejected(bad, match):
    ctx = factpin.Context("results")
    with pytest.raises(ValueError, match=match):
        ctx.add_text("x", bad)


def test_escaped_brace_and_percent_are_not_miscounted():
    ctx = factpin.Context("results")
    ctx.add_text("x", r"100\% of \{cases\}")
    assert ctx.constants[0].values == [r"100\% of \{cases\}"]


def test_text_must_be_a_string():
    ctx = factpin.Context("results")
    with pytest.raises(TypeError, match="must be a str"):
        ctx.add_text("x", 1)


def test_duplicate_group_rejected():
    ctx = factpin.Context("results")
    ctx.add_group("auroc", places=3)
    with pytest.raises(ValueError, match="already declared"):
        ctx.add_group("auroc", places=2)


def test_arity_mismatch_caught_in_python():
    ctx = factpin.Context("results")
    ctx.add_group("auroc", places=3, format="ci")
    with pytest.raises(ValueError, match="expects 3 value"):
        ctx.add("x", values=[0.5, 0.4], group="auroc")


def test_places_and_sigfigs_are_exclusive():
    ctx = factpin.Context("results")
    with pytest.raises(ValueError, match="not both"):
        ctx.add_group("g", places=2, sigfigs=3)


def test_siunitx_options_translation():
    g = factpin.Group("g", places=3)
    assert g.siunitx_options() == "round-mode=places,round-precision=3"

    g = factpin.Group("g", sigfigs=2)
    assert g.siunitx_options() == "round-mode=figures,round-precision=2"

    g = factpin.Group("g")
    assert g.siunitx_options() == ""

    # The escape hatch is appended last so it always wins.
    g = factpin.Group("g", places=1, siunitx="round-mode=places,round-precision=4")
    assert g.siunitx_options().endswith("round-precision=4")


@pytest.mark.parametrize("flag, expected", [(True, r"\texttt{True}"), (False, r"\texttt{False}")])
def test_bool_is_pinned_as_text(flag, expected):
    ctx = factpin.Context("results")
    c = ctx.add("converged", value=flag)
    assert c.text
    assert c.values == [expected]
    assert f"\\declconsttext{{converged}}{{{expected}}}" in ctx.render()


def test_numpy_bool_is_pinned_as_text():
    np = pytest.importorskip("numpy")
    ctx = factpin.Context("results")
    assert ctx.add("converged", value=np.bool_(True)).values == [r"\texttt{True}"]


@pytest.mark.parametrize(
    "kwargs", [{"values": [True, False]}, {"values": [0.5, True]}, {"value": True, "group": "g"}]
)
def test_bool_outside_a_lone_value_is_rejected(kwargs):
    ctx = factpin.Context("results")
    ctx.add_group("g")
    with pytest.raises(TypeError, match="bool"):
        ctx.add("flag", **kwargs)
