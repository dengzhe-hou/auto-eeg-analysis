"""Cold-start deployability: does a fresh checkout of this repo actually work?

These checks originated before the external Windows runs recorded in
docs/FIRST_EXTERNAL_TEST.md. A clean clone remains a precondition for external use.

These tests lock in two defects a cold-start deployment test found that the rest of the suite
could not, because the rest of the suite runs in the developer's own checkout where the missing
things happen to be present.

Scope, stated honestly: this proves the repo is self-contained and free of paths tied to one
checkout. It does not prove AEA works on another machine, another OS, or for another person.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "tools" / "validation"

CERTIFIED = {
    "validate_mmn_group.py": "mmn_group_results.json",
    "validate_p3_group.py": "p3_group_results.json",
    "validate_n170_erpcore_group.py": "n170_erpcore_results.json",
    "validate_ern_erpcore_group.py": "ern_erpcore_results.json",
    "validate_n400_erpcore_group.py": "n400_erpcore_results.json",
}

# Scripts and data that are reference artefacts of one particular run, not things a user executes.
PATH_LEAK_EXEMPT = ("cross_toolbox_results/", "generated_pipelines/", "review-stage/",
                    "mmn_eeglab.m", "/projects/")


def _executable_sources() -> list[Path]:
    out = []
    for pat in ("tools/**/*.py", "tools/**/*.m", "tools/**/*.sh", "templates/**/*.m",
                "skills/**/*.md"):
        for p in ROOT.glob(pat):
            rel = p.relative_to(ROOT).as_posix()
            if not any(x.strip("/") in rel for x in PATH_LEAK_EXEMPT):
                out.append(p)
    return out


def test_no_developer_home_paths_in_executable_sources():
    """A hardcoded /home/<someone> path makes a script work only in one checkout.

    Found by cold-start test: erpcore_eeglab.m and erpcore_fieldtrip.m defaulted to this
    developer's data directory and to a FieldTrip copy living inside a *gitignored* folder, so the
    documented reproduce command could not run from a fresh clone.
    """
    offenders = []
    pat = re.compile(r"/home/[a-z][a-z0-9_-]*/", re.I)
    for p in _executable_sources():
        for i, line in enumerate(p.read_text(errors="ignore", encoding="utf-8-sig").splitlines(), 1):
            if line.lstrip().startswith(("#", "%", "//")):
                continue                      # a comment or doc example is not a runtime path
            if pat.search(line):
                offenders.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
    assert not offenders, (
        "hardcoded developer home paths make these unrunnable from a fresh clone:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.parametrize("script,results", sorted(CERTIFIED.items()))
def test_validation_scripts_guard_the_certified_baseline(script, results):
    """A partial run must not be able to overwrite the file the CI gate certifies against.

    Found by cold-start test: `validate_mmn_group.py --subjects 3` silently replaced a 38-subject
    certified baseline with a 3-subject smoke run. test_benchmark.py then failed — but only after
    the reference was already gone.
    """
    src = (VALIDATION / script).read_text(encoding="utf-8-sig")
    assert "guard_certified_output" in src, f"{script} does not guard its --out default"
    assert '"--force"' in src, f"{script} has no --force escape hatch for deliberate re-certification"
    # the guard must run before the write, not after
    assert src.index("guard_certified_output(args.out") < src.index("json.dump(results"), (
        f"{script} guards after writing, which is too late")


def test_guard_blocks_a_partial_run_and_allows_a_matching_one(tmp_path):
    sys.path.insert(0, str(VALIDATION))
    from _certified_output import guard_certified_output

    baseline = tmp_path / "certified.json"
    baseline.write_text(json.dumps({"n_subjects": 38}), encoding="utf-8")

    guard_certified_output(baseline, baseline, n_new=38)                 # same N -> allowed
    guard_certified_output(baseline, baseline, n_new=3, force=True)      # explicit override
    guard_certified_output(tmp_path / "elsewhere.json", baseline, n_new=3)  # different target

    with pytest.raises(SystemExit) as e:
        guard_certified_output(baseline, baseline, n_new=3)             # partial run -> blocked
    assert e.value.code == 3


def _find_posix_bash() -> str | None:
    """A bash that can actually run a POSIX script, not the WSL launcher stub."""
    import shutil
    cands = [shutil.which("bash")]
    if os.name == "nt":
        cands += [r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"]
    for c in cands:
        if not c:
            continue
        if os.name == "nt" and "system32" in c.lower():
            continue                       # the WSL launcher, not a shell we can drive
        try:
            r = subprocess.run([c, "-c", "echo ok"], capture_output=True, text=True, timeout=30)
        except Exception:                  # noqa: BLE001
            continue
        if r.returncode == 0 and "ok" in (r.stdout or ""):
            return c
    return None


def test_env_probe_emits_valid_json_when_optional_packages_are_missing(tmp_path):
    """The probe must survive a bare environment — every skill is required to read its output.

    A previous version emitted an empty field for each missing package (the `|| echo` fallback
    never fired, because a pipeline's exit status is the last command's), which made the whole
    ENVIRONMENT.json unparseable on exactly the machines that most needed the report.
    """
    out = tmp_path / "ENVIRONMENT.json"
    # `bash` on Windows resolves to C:\Windows\System32\bash.exe -- the WSL launcher, not Git
    # Bash. It exits 1 and emits UTF-16, so this test reported a red FAIL that described the
    # tester's machine rather than AEA. Exactly the Store-python3-stub trap, one layer down:
    # a name on PATH is not the program you meant. Prefer a real POSIX shell, else skip.
    bash = _find_posix_bash()
    if bash is None:
        pytest.skip("no POSIX bash found (on Windows, install Git Bash; System32\\bash.exe is WSL)")
    r = subprocess.run([bash, str(ROOT / "tools" / "env" / "check_env.sh"), str(out)],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    env = json.loads(out.read_text(encoding="utf-8-sig"))          # the assertion that matters: it parses
    assert env["schema_version"] == "3"
    for group in ("python_packages", "optional_packages"):
        for pkg, spec in env[group].items():
            assert isinstance(spec, dict) and "available" in spec, f"{group}.{pkg} is malformed"


# --- the first-external-test promise -----------------------------------------------------------
# docs/FIRST_EXTERNAL_TEST.md tells a tester they need only "Python with mne, numpy, scipy and
# pytest". Five separate unguarded imports have already broken that promise; each one turns a
# first-time tester's report into a wall of red about their environment rather than about AEA.

# mne's own install_requires, checked against importlib.metadata rather than hand-maintained.
MNE_CORE = {"decorator", "jinja2", "lazy_loader", "matplotlib", "numpy", "packaging",
            "pooch", "scipy", "tqdm"}
# The stdlib is enumerated by the interpreter, not by a list that silently rots.
ALWAYS_OK = MNE_CORE | set(sys.stdlib_module_names) | {"mne", "pytest"}


def _module_roots(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                yield n, a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            yield n, n.module.split(".")[0]


@pytest.mark.parametrize("path", sorted((ROOT / "tools" / "tests").glob("test_*.py")),
                         ids=lambda p: p.name)
def test_no_unguarded_non_core_imports(path):
    """Anything outside mne's core dependency set must be behind pytest.importorskip."""
    src = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    guarded = {
        n.args[0].value.split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "importorskip" and n.args and isinstance(n.args[0], ast.Constant)
    }
    # Local project modules resolved via sys.path manipulation are not third-party.
    # This includes the figure builders in tools/benchmark/reports/.
    local = {p.stem for p in (ROOT / "tools").rglob("*.py")}
    offenders = sorted({
        m for _, m in _module_roots(tree)
        if m not in ALWAYS_OK and m not in guarded and m not in local and not m.startswith("_")
    })
    assert not offenders, (
        f"{path.name} imports {offenders} without pytest.importorskip. These are not core mne "
        f"dependencies, so a tester following docs/FIRST_EXTERNAL_TEST.md would see failures "
        f"about their environment instead of a usable report."
    )


@pytest.mark.parametrize("ps", sorted(ROOT.glob("**/*.ps1")), ids=lambda p: p.name)
def test_powershell_scripts_are_ascii_only(ps):
    """Windows PowerShell 5.1 decodes a BOM-less UTF-8 .ps1 as ANSI.

    A single non-ASCII byte therefore breaks PARSING, not merely display -- the script does not
    run at all. This was originally fixed for deploy_report.ps1 only, while check_env.ps1 (which
    deploy_report.ps1 *calls*) still carried a non-ASCII character. Parametrising over every .ps1
    is what makes that class of half-fix impossible.
    """
    bad = [(i, l) for i, l in enumerate(ps.read_text(encoding="utf-8-sig").splitlines(), 1)
           if any(ord(c) > 127 for c in l)]
    assert not bad, f"non-ASCII in {ps.name} breaks parsing on PowerShell 5.1: {bad[:3]}"


def test_deploy_report_scripts_exist():
    assert (ROOT / "tools" / "env" / "deploy_report.sh").exists()
    assert (ROOT / "tools" / "env" / "deploy_report.ps1").exists()


def test_shell_scripts_are_lf_only():
    """A CRLF .sh reaches a Linux tester as `\r: command not found` -- broken before it starts."""
    offenders = [p.relative_to(ROOT).as_posix() for p in ROOT.glob("**/*.sh")
                 if b"\r\n" in p.read_bytes()]
    assert not offenders, f"CRLF line endings in shell scripts: {offenders}"


def test_gitattributes_pins_line_endings():
    ga = ROOT / ".gitattributes"
    assert ga.exists(), "no .gitattributes: a Windows committer can put CRLF into a .sh"
    txt = ga.read_text(encoding="utf-8-sig")
    assert "*.sh text eol=lf" in txt


def test_deploy_report_never_leaves_a_blank_failure_section():
    """A blank failure report is the one outcome that makes the external test worthless."""
    src = (ROOT / "tools" / "env" / "deploy_report.sh").read_text(encoding="utf-8-sig")
    assert "no pytest summary line" in src, "missing fallback when pytest dies before summarising"
    assert "tail -60" in src, "missing raw-output fallback for the failure detail block"
    assert "BLOCKED" in src, "missing an explicit blocked-run verdict"
    assert "pip install" in src, "a blocked run must say how to fix it"


def test_deploy_report_honours_an_explicit_interpreter():
    """AEA_PYTHON is an instruction. Substituting a 'better' interpreter hides the tested machine."""
    for f in ("deploy_report.sh", "deploy_report.ps1"):
        src = (ROOT / "tools" / "env" / f).read_text(encoding="utf-8-sig")
        assert "AEA_PYTHON is set to" in src, f"{f} does not honour an explicit AEA_PYTHON"


def _open_mode(call):
    """Return the mode expression for open(path, mode) or Path.open(mode)."""
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return keyword.value
    index = 0 if isinstance(call.func, ast.Attribute) else 1
    return call.args[index] if len(call.args) > index else ast.Constant(value="r")


# --- three defects found by a real Windows run of main, all the same shape ---------------------
# Each is "a name that exists is not the thing you meant", or "a default that differs by platform".
# None could be reproduced on the developer's Linux box; all three broke the external-test path.

@pytest.mark.parametrize(
    "path",
    sorted(p for p in (ROOT / "tools").rglob("*.py") if "generated_pipelines" not in str(p)),
    ids=lambda p: p.name,
)
def test_text_io_declares_an_encoding(path):
    """Unencoded text IO uses the locale codec, which is cp1252 on Windows.

    resolve_backend.py wrote a report containing arrows, em-dashes and 'µ' via
    Path.write_text() with no encoding, so it raised UnicodeEncodeError on EVERY Windows machine
    -- at step 2 of the report we ask external testers to run. The reporter found one call site;
    the repo had 97.
    """
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    bad = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        if name not in {"write_text", "read_text", "open"}:
            continue
        if any(k.arg == "encoding" for k in n.keywords):
            continue
        if name == "open":
            mode = _open_mode(n)
            if isinstance(mode, ast.Constant) and "b" in str(mode.value):
                continue                       # binary mode takes no encoding
            if mode is not None and not isinstance(mode, ast.Constant):
                continue                       # dynamic mode, cannot decide statically
        bad.append(n.lineno)
    assert not bad, (
        f"{path.relative_to(ROOT)} lines {bad}: text IO without encoding= falls back to the "
        f"locale codec (cp1252 on Windows) and raises UnicodeEncodeError on non-ASCII content."
    )


def test_powershell_executable_is_resolved_not_assumed():
    """Windows ships powershell.exe (5.1); pwsh (7) is a separate install.

    deploy_report.ps1 hardcoded `pwsh`, so on a stock Windows box it died with
    CommandNotFoundException and the report blamed check_env.ps1 -- which was fine.
    """
    src = (ROOT / "tools" / "env" / "deploy_report.ps1").read_text(encoding="utf-8-sig")
    assert "& pwsh -NoProfile" not in src, "deploy_report.ps1 still invokes pwsh unconditionally"
    assert "$psExe" in src, "deploy_report.ps1 does not resolve a PowerShell executable"
    # anything we tell the user to type must name a shell a stock Windows box actually has
    for line in src.splitlines():
        if "Add-Out" in line and "deploy_report.ps1" in line and "pwsh" in line:
            assert "powershell" in line, f"instruction names only pwsh: {line.strip()}"


def test_bash_is_resolved_not_assumed():
    """`bash` on Windows is C:\\Windows\\System32\\bash.exe -- the WSL launcher, not a shell.

    Same trap as the Microsoft Store python3 stub: present on PATH, not the program meant.
    """
    # Checked via the AST, not by string search: the string "bash" appears in this very
    # assertion, so a textual check would flag itself.
    offenders = []
    for path in (ROOT / "tools").rglob("*.py"):
        if "generated_pipelines" in str(path):
            continue
        for n in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if not (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "run"):
                continue
            if not n.args or not isinstance(n.args[0], ast.List) or not n.args[0].elts:
                continue
            first = n.args[0].elts[0]
            if isinstance(first, ast.Constant) and first.value in {"bash", "sh", "pwsh"}:
                offenders.append(f"{path.relative_to(ROOT)}:{n.lineno} -> {first.value!r}")
    assert not offenders, (
        "a bare interpreter name is not the program you meant on Windows "
        f"(System32\\bash.exe is the WSL launcher; pwsh may not exist): {offenders}"
    )


# --- round 2 of the real-Windows run: BOM, redaction shapes, crash-vs-refusal -------------------

@pytest.mark.parametrize(
    "path",
    sorted(p for p in (ROOT / "tools").rglob("*.py") if "generated_pipelines" not in str(p)),
    ids=lambda p: p.name,
)
def test_text_reads_tolerate_a_bom(path):
    """PowerShell 5.1 ALWAYS writes UTF-8 with a BOM, so anything it produces starts EF BB BF.

    check_env.ps1 emits ENVIRONMENT.json; resolve_backend.py read it with encoding="utf-8" and
    died with `Unexpected UTF-8 BOM`. That break was *unlocked* by fixing the pwsh hardcode --
    before that, step 1 produced no file at all, so step 2 never saw one.

    Reads must use utf-8-sig (which also reads BOM-less files); writes stay utf-8 so we never
    emit a BOM ourselves.
    """
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    bad = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        is_read = name == "read_text"
        if name == "open":
            mode = _open_mode(n)
            m = mode.value if isinstance(mode, ast.Constant) else "r"
            if "b" in str(m):
                continue
            is_read = "r" in str(m) and "+" not in str(m)
        if not is_read:
            continue
        for kw in n.keywords:
            if kw.arg == "encoding" and isinstance(kw.value, ast.Constant) \
                    and kw.value.value == "utf-8":
                bad.append(kw.value.lineno)
    assert not bad, (
        f"{path.relative_to(ROOT)} lines {bad}: a text READ pinned to 'utf-8' rejects a "
        f"BOM-prefixed file, which is exactly what PowerShell 5.1 writes. Use 'utf-8-sig'."
    )


def test_redaction_covers_every_path_shape():
    """A home path appears in the report literal, JSON/repr-escaped, and slash-flipped.

    The Windows run leaked a real username through the escaped form inside an embedded
    ENVIRONMENT.json: redaction matched `C:\\Users\\name` while the file contained
    `C:\\\\Users\\\\name`. This report gets emailed, so a partial redaction is a privacy defect.
    """
    ps = (ROOT / "tools" / "env" / "deploy_report.ps1").read_text(encoding="utf-8-sig")
    sh = (ROOT / "tools" / "env" / "deploy_report.sh").read_text(encoding="utf-8-sig")
    # escaped-backslash form and forward-slash form, matched literally against the source
    assert r"Replace('\','\\')" in ps, "ps1 does not redact the escaped-backslash form"
    assert r"Replace('\','/')" in ps, "ps1 does not redact the forward-slash form"
    # bare-username backstop in both
    assert "<user>" in ps and "<user>" in sh, "no bare-username backstop"
    # ...and the check must be CALLED, not merely defined. The original assertion only looked for
    # the name, which a dead function satisfies -- and it did: Assert-NoLeak was defined and never
    # invoked, so the first real Windows run reported "no WARNING line" from a check that never
    # ran. A test that a guard exists is not a test that the guard runs.
    calls = [ln for ln in ps.splitlines()
             if "Assert-NoLeak" in ln and not ln.lstrip().startswith(("#", "function"))]
    assert calls, "ps1 defines Assert-NoLeak but never calls it"
    assert "still appears in" in sh, "the bash report has no redaction self-check at all"


def test_report_does_not_call_a_crash_a_legitimate_outcome():
    """A crash and a designed refusal both exit non-zero.

    The Windows report printed "Resolver declined. That is a legitimate outcome" directly above a
    Python traceback -- so a reader would conclude step 2 was healthy. That is the project's own
    silent-degradation failure mode, one layer up, inside the instrument that is supposed to catch
    it.
    """
    for f in ("deploy_report.sh", "deploy_report.ps1"):
        src = (ROOT / "tools" / "env" / f).read_text(encoding="utf-8-sig")
        assert "Traceback" in src, f"{f} cannot tell a crash from a refusal"
        assert "CRASH" in src, f"{f} has no distinct label for an unhandled exception"


# --- cross-language syntax leaks ---------------------------------------------------------------

CROSS_LANGUAGE_LEAKS = {
    ".ps1": [
        (r'"""', "Python docstring - in PowerShell this is a string EXPRESSION that lands in "
                 "the function's output stream"),
        (r"^\s*def\s+\w+\s*\(", "Python function definition"),
        (r"^\s*elif\b", "Python/bash elif (PowerShell uses elseif)"),
        (r"^\s*#!/", "shebang - meaningless in PowerShell"),
    ],
    ".sh": [
        (r"\bWrite-Host\b", "PowerShell cmdlet"),
        (r"\$PSVersionTable", "PowerShell automatic variable"),
        (r"^\s*\"\"\"", "Python docstring"),
        (r"\belseif\b", "PowerShell elseif (bash uses elif)"),
    ],
    ".m": [
        (r"^\s*\"\"\"", "Python docstring"),
        (r"^\s*def\s+\w+\s*\(", "Python function definition"),
        (r"\bWrite-Host\b", "PowerShell cmdlet"),
    ],
    ".py": [
        (r"\bWrite-Host\b", "PowerShell cmdlet"),
        (r"^\s*elseif\b", "PowerShell elseif"),
    ],
}

_LEAK_SKIP = ("generated_pipelines", "review-stage", "projects/", "MCKJ0914",
              "AnalyzingNeuralTimeSeries", "Python-EEG-Handbook")


@pytest.mark.parametrize("ext", sorted(CROSS_LANGUAGE_LEAKS))
def test_no_cross_language_syntax_leaks(ext):
    """One language's syntax written into another file type, where it is silently WRONG.

    Found on a real Windows run: a Python docstring inside a PowerShell function. It broke nothing
    visible because the function's output was discarded -- which is precisely why a reader would
    never notice. Anything that produced a hard syntax error would already have been caught, so
    this class is defined by being quiet.
    """
    offenders = []
    for p in sorted(ROOT.rglob(f"*{ext}")):
        rel = p.relative_to(ROOT).as_posix()
        if any(s.strip("/") in rel for s in _LEAK_SKIP):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8-sig", errors="ignore").splitlines(), 1):
            for pat, why in CROSS_LANGUAGE_LEAKS[ext]:
                if re.search(pat, line):
                    offenders.append(f"{rel}:{i} -> {why}")
    assert not offenders, "cross-language syntax leak:\n  " + "\n  ".join(offenders)
