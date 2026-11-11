# SPDX-FileCopyrightText: 2026 Benjamin C. Warner
# SPDX-License-Identifier: MIT

"""Compile real documents and assert on what factpin.sty actually emitted.

Two tiers:

* The *stub* tests replace siunitx with a recorder (tests/latex/stub/siunitx.sty) that
  logs every call, so factpin.sty's group lookup, format dispatch and unit handling are
  verified on any TeX installation.
* The *siunitx* tests compile against the real package and are skipped when it is not
  installed (Debian/Ubuntu: ``apt install texlive-science``).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import factpin

STUB_DIR = Path(__file__).parent / "latex" / "stub"

pytestmark = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="pdflatex not installed"
)


def _has_siunitx() -> bool:
    kpsewhich = shutil.which("kpsewhich")
    if kpsewhich is None:
        return False
    return subprocess.run([kpsewhich, "siunitx.sty"], capture_output=True).returncode == 0


needs_siunitx = pytest.mark.skipif(
    not _has_siunitx(), reason="siunitx not installed (apt install texlive-science)"
)


def compile_tex(workdir: Path, body: str, *, stub: bool, halt: bool = True):
    """Run pdflatex on a document and return (returncode, log text)."""
    factpin.install_sty(workdir)
    if stub:
        shutil.copyfile(STUB_DIR / "siunitx.sty", workdir / "siunitx.sty")

    (workdir / "doc.tex").write_text(
        "\\documentclass{article}\n"
        "\\usepackage{factpin}\n"
        "\\begin{document}\n"
        f"{body}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    # Stop TeX wrapping \typeout and warning lines at 79 columns, which would otherwise
    # split the strings these tests grep for.
    env["max_print_line"] = "10000"
    env["error_line"] = "254"
    env["half_error_line"] = "238"
    # Search the working directory first so the stub siunitx wins over an installed one
    # no matter what TEXINPUTS the caller has set.
    env["TEXINPUTS"] = f"{workdir}:{os.environ.get('TEXINPUTS', '')}"

    cmd = ["pdflatex", "-interaction=nonstopmode"]
    if halt:
        cmd.append("-halt-on-error")
    cmd.append("doc.tex")

    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, env=env)
    log = (workdir / "doc.log").read_text(encoding="utf-8", errors="replace")
    # l3msg wraps its own errors and warnings at ~78 columns and prefixes the
    # continuation lines with "(factpin)"; undo that so assertions can span a message.
    log = re.sub(r"\n\(factpin\)\s*", " ", log)
    return proc.returncode, log


def fixture_declarations(tmp_path: Path) -> str:
    """Generate declarations with the real Python API, so the two sides are tested together."""
    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_group("auroc", places=3, format="ci")
    ctx.add_group("latency", unit=r"\milli\second", places=1)
    ctx.add_group("scores", places=2, format="list")
    ctx.add("auroc_a_mean", value=0.5, group="auroc")
    ctx.add("auroc_a_ci", values=[0.5017, 0.4523, 0.5488], group="auroc")
    ctx.add("train_time", value=12.34, group="latency")
    ctx.add("folds", values=[0.81, 0.79, 0.83], group="scores")
    ctx.add("n_patients", value=1234)
    ctx.add("never_used", value=99)
    ctx.write()
    return "\\input{results}"


def test_stub_dispatches_the_right_siunitx_call_per_group(tmp_path):
    body = (
        fixture_declarations(tmp_path) + "\n"
        "A \\const{n_patients} B \\const{auroc_a_mean} C \\const{auroc_a_ci} "
        "D \\const{train_time} E \\const{folds}\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log

    calls = [line for line in log.splitlines() if line.startswith("FACTPIN|")]

    # No group -> plain \num, no options, no unit.
    assert "FACTPIN|num||1234|" in calls

    # Group with rounding, no unit -> \num carrying the group's options.
    assert "FACTPIN|num|round-mode=places,round-precision=3|0.5|" in calls

    # ci format -> point estimate as \num, interval as \numrange, same options.
    assert "FACTPIN|num|round-mode=places,round-precision=3|0.5017|" in calls
    assert (
        "FACTPIN|numrange|round-mode=places,round-precision=3|0.4523|0.5488|" in calls
    )

    # Group with a unit -> \qty, unit passed through verbatim.
    assert any(
        c.startswith("FACTPIN|qty|round-mode=places,round-precision=1|12.34|")
        and "milli" in c
        and "second" in c
        for c in calls
    ), calls

    # list format -> \numlist with siunitx's semicolon separator.
    assert "FACTPIN|numlist|round-mode=places,round-precision=2|0.81;0.79;0.83|" in calls


def test_stub_labels_each_constant_at_its_first_use(tmp_path):
    body = (
        fixture_declarations(tmp_path) + "\n"
        "First \\const{auroc_a_mean} and again \\const{auroc_a_mean}.\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log

    aux = (tmp_path / "doc.aux").read_text(encoding="utf-8")
    # Labelled exactly once despite two uses -- no duplicate-label warning.
    assert aux.count("\\newlabel{const:auroc_a_mean}") == 1
    assert "There were multiply-defined labels" not in log
    # A constant that is declared but never typeset gets no label.
    assert "\\newlabel{const:never_used}" not in aux


def test_stub_warns_about_declared_but_unused_constants(tmp_path):
    body = fixture_declarations(tmp_path) + "\nOnly \\const{n_patients} is used.\n"
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    assert "never_used" in log
    assert "declared but never used" in log
    # The one that *is* used must not be reported.
    assert "Constant 'n_patients' is declared but never used" not in log


def test_stub_warning_can_be_switched_off(tmp_path):
    body = (
        "\\constsetup{warn-unused=false}\n"
        + fixture_declarations(tmp_path)
        + "\nOnly \\const{n_patients} is used.\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    assert "declared but never used" not in log


def test_stub_constvalue_is_expandable_and_raw(tmp_path):
    body = (
        fixture_declarations(tmp_path) + "\n"
        "\\typeout{RAW1:\\constvalue{auroc_a_mean}:}\n"
        "\\typeout{RAW2:\\constvalue[2]{auroc_a_ci}:}\n"
        "\\edef\\x{\\constvalue{train_time}}\\typeout{RAW3:\\x:}\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    assert "RAW1:0.5:" in log
    assert "RAW2:0.4523:" in log
    # Survives \edef, i.e. genuinely expandable -- usable in pgfplots coordinates.
    assert "RAW3:12.34:" in log


def test_stub_text_constant_is_typeset_verbatim(tmp_path):
    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_text("best_model", r"Logistic regression (\textsc{l1})")
    ctx.add_text("best_task", "PHQ-9")
    ctx.write()
    body = (
        "\\input{results}\n"
        # \const is protected (it labels and records use), so it cannot expand inside
        # \typeout. Typeset it into a box and compare against the literal text instead.
        "\\setbox0=\\hbox{\\const{best_task}}\\setbox2=\\hbox{PHQ-9}\n"
        "\\typeout{TEXT1:\\ifdim\\wd0=\\wd2 same\\else differs\\fi:}\n"
        "Model: \\const{best_model}.\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    # Text never reaches siunitx -- no \num, \qty or friends are called for it.
    assert not [line for line in log.splitlines() if line.startswith("FACTPIN|")]
    assert "TEXT1:same:" in log
    assert "declared but never used" not in log


def test_stub_text_constant_is_labelled_like_a_number(tmp_path):
    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_text("best_model", "Logistic regression")
    ctx.write()
    body = "\\input{results}\nA \\const{best_model} B \\const{best_model}."
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    aux = (tmp_path / "doc.aux").read_text(encoding="utf-8")
    assert aux.count("\\newlabel{const:best_model}") == 1


def test_stub_unused_text_constant_is_warned_about(tmp_path):
    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_text("stale_name", "Something nobody cites")
    ctx.add("n", value=1)
    ctx.write()
    rc, log = compile_tex(tmp_path, "\\input{results}\nOnly \\const{n}.", stub=True)
    assert rc == 0, log
    assert "Constant 'stale_name' is declared but never used" in log


def test_stub_constvalue_on_text_reports_it_has_no_number(tmp_path):
    # A text constant may contain commas; \constvalue splits on commas, so handing back
    # a truncated fragment would be worse than refusing.
    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_text("best_model", "Logistic regression, L1")
    ctx.write()
    body = "\\input{results}\nRaw: \\constvalue{best_model}."
    rc, log = compile_tex(tmp_path, body, stub=True, halt=False)
    assert rc != 0
    # Expandable errors are truncated to one line, so only the leading words survive --
    # which is exactly why the message starts with them.
    assert "Text constant" in log


def test_stub_unknown_constant_is_a_hard_error(tmp_path):
    rc, log = compile_tex(
        tmp_path, "Value: \\const{no_such_thing}.", stub=True, halt=False
    )
    assert rc != 0
    assert "Constant 'no_such_thing' is not defined" in log


def test_stub_arity_mismatch_is_a_hard_error(tmp_path):
    body = (
        "\\declconstgroup{g}{}{}{ci}\n"
        "\\declconst{bad}{0.5,0.4}{g}\n"
        "Value: \\const{bad}.\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True, halt=False)
    assert rc != 0
    assert "expects 3" in log


def test_stub_undeclared_group_is_a_hard_error(tmp_path):
    body = "\\declconst{orphan}{0.5}{nogroup}\nValue: \\const{orphan}.\n"
    rc, log = compile_tex(tmp_path, body, stub=True, halt=False)
    assert rc != 0
    assert "undeclared group 'nogroup'" in log


def test_stub_custom_format(tmp_path):
    body = (
        "\\defineconstformat[2]{over}{\\factpinnum{#1}/\\factpinnum{#2}}\n"
        "\\declconstgroup{g}{}{}{over}\n"
        "\\declconst{frac}{3,4}{g}\n"
        "Value: \\const{frac}.\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    assert "FACTPIN|num||3|" in log
    assert "FACTPIN|num||4|" in log


def test_stub_ci_label_default_and_override(tmp_path):
    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available for text extraction")
    body = (
        "\\declconstgroup{g}{}{}{ci}\n"
        "\\declconst{x}{0.5,0.4,0.6}{g}\n"
        "A \\const{x} B\n\n"
        "\\constsetup{ci-label={90\\% CI}}\n"
        "C \\const{x} D\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=True)
    assert rc == 0, log
    subprocess.run(
        ["pdftotext", "doc.pdf", "doc.txt"], cwd=tmp_path, check=True, capture_output=True
    )
    text = " ".join((tmp_path / "doc.txt").read_text(encoding="utf-8").split())
    # The stub typesets no numbers, so only factpin's own text is left in the PDF.
    assert "A (95% CI: ) B" in text
    # A custom label is used exactly as written; the colon is not added for it.
    assert "C (90% CI ) D" in text


@needs_siunitx
def test_real_siunitx_compiles_and_rounds(tmp_path):
    body = (
        fixture_declarations(tmp_path) + "\n"
        "A \\const{n_patients} B \\const{auroc_a_ci} C \\const{train_time} "
        "D \\const{folds}\n"
    )
    rc, log = compile_tex(tmp_path, body, stub=False)
    assert rc == 0, log

    if shutil.which("pdftotext") is None:
        pytest.skip("pdftotext not available for text extraction")

    subprocess.run(
        ["pdftotext", "doc.pdf", "doc.txt"], cwd=tmp_path, check=True, capture_output=True
    )
    text = (tmp_path / "doc.txt").read_text(encoding="utf-8", errors="replace")
    text = text.replace("\u2212", "-").replace("\u2013", "-").replace("\u2009", " ")
    text = " ".join(text.split())

    assert "1234" in text
    assert "0.502" in text  # rounded to the group's 3 places
    # Note the space after the label: a control word eats a following space in the
    # format template, which silently glued these together at one point.
    assert "95% CI: 0.452" in text
    assert "0.549" in text
    assert "12.3 ms" in text  # rounded to 1 place, unit from the group


@needs_siunitx
def test_real_siunitx_example_project_compiles(tmp_path):
    examples = Path(__file__).resolve().parents[1] / "examples"
    if not (examples / "manuscript.tex").is_file():
        pytest.skip("examples/ not present (it is not tracked or shipped in the sdist)")
    for name in ("manuscript.tex", "analysis.py"):
        shutil.copyfile(examples / name, tmp_path / name)
    factpin.install_sty(tmp_path)

    ctx = factpin.Context("results", path=tmp_path)
    ctx.add_group("auroc", places=3, format="ci")
    ctx.add_group("latency", unit=r"\milli\second", places=1)
    ctx.add_group("pct", unit=r"\percent", places=1)
    ctx.add("auroc_a_mean", value=0.5017, group="auroc")
    ctx.add("auroc_a_ci", values=[0.5017, 0.4523, 0.5488], group="auroc")
    ctx.add("train_time", value=12.3456, group="latency")
    ctx.add("coverage", value=94.27, group="pct")
    ctx.add("n_patients", value=1234)
    ctx.add_text("best_model", r"logistic regression (\textsc{l1})")
    ctx.write()

    env = dict(os.environ)
    env["max_print_line"] = "10000"
    for _ in range(2):  # second pass resolves \pageref
        proc = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "manuscript.tex"],
            cwd=tmp_path,
            capture_output=True,
            env=env,
        )
    log = (tmp_path / "manuscript.log").read_text(encoding="utf-8", errors="replace")
    assert proc.returncode == 0, log
    assert "declared but never used" not in log
