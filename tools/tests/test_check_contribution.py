import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
import check_contribution as cc
from scrub_privacy import find_pii

COURSE = "Semesters/Semester 5 (5ο Εξάμηνο)/Λειτουργικά Συστήματα - CEID_24Y330"
EXAMS = f"docs/{COURSE}/Previous Exams"

SESSION = """---
course: CEID_24Y330
session: 2025-06
label: Ιούνιος 2025
sources: [2025-06.pdf]
format: open
transcription: verbatim
solutions: {sol}
---
# Θέμα 1
Εξηγήστε τι είναι διεργασία.
"""
SOLUTIONS = """---
course: CEID_24Y330
session: 2025-06
status: {status}
source: community
{extra}---
# Θέμα 1
Μια διεργασία είναι πρόγραμμα σε εκτέλεση.
"""
README = "# Exams\n\n<!-- BEGIN:sessions -->\n<!-- END:sessions -->\n"


def w(root, rel, text="", data=None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if data is not None:
        p.write_bytes(data)
    else:
        p.write_text(text, encoding="utf-8", newline="\n")
    return rel


@pytest.fixture
def repo(tmp_path):
    w(tmp_path, f"{EXAMS}/README.md", README)
    w(tmp_path, f"{EXAMS}/2025-06.md", SESSION.format(sol="none"))
    return tmp_path


def run(root, *paths, owner=False, status="M"):
    return cc.check(root, [cc.Change(status, p) for p in paths], owner=owner)


def test_valid_exam_passes_exam_validator(repo):
    rep = cc.check(repo, [cc.Change("M", f"{EXAMS}/2025-06.md")])
    exam_errs = [e for e in rep.errors if "Previous Exams" in e]
    assert exam_errs == []


def test_rejects_files_outside_docs(repo):
    w(repo, "tools/x.md", "hi")
    rep = run(repo, "tools/x.md")
    assert any("only files under docs/" in e for e in rep.errors)
    assert run(repo, "tools/x.md", owner=True).errors == []


def test_rejects_binary_and_extension(repo):
    w(repo, f"{EXAMS}/scan.png", data=b"\x89PNG\0\0")
    rep = run(repo, f"{EXAMS}/scan.png")
    assert any("not allowed" in e for e in rep.errors)


def test_rejects_nul_in_md(repo):
    w(repo, "docs/a.md", data=b"abc\0def")
    assert any("binary" in e for e in run(repo, "docs/a.md").errors)


def test_size_limit(repo):
    w(repo, "docs/big.md", "x" * (201 * 1024))
    assert any("200 KB" in e for e in run(repo, "docs/big.md").errors)


def test_deletion_contributor_vs_owner(repo):
    assert run(repo, "docs/gone.md", status="D").errors
    assert run(repo, "docs/gone.md", status="D", owner=True).errors == []


def test_privacy_reports_line_without_echo(repo):
    w(repo, "docs/note.md", "ok\nτηλ 6912345678 εδώ\nup1234567\n")
    rep = run(repo, "docs/note.md")
    msgs = [e for e in rep.errors if "privacy" in e]
    assert any(":2:" in m for m in msgs) and any(":3:" in m for m in msgs)
    assert not any("6912345678" in m or "up1234567" in m for m in msgs)


def test_find_pii_patterns():
    assert find_pii("mail me at john@gmail.com")
    assert find_pii("https://cdn.discordapp.com/attachments/1/2/file.png?ex=1")
    assert find_pii("<@123456789012345678>")
    assert find_pii("Α.Μ. 1234567")
    assert find_pii("Καθηγητής, τηλ 2610996000") == []
    assert find_pii("clean text") == []


def test_verified_needs_fields(repo):
    w(repo, f"{EXAMS}/2025-06.md", SESSION.format(sol="verified"))
    w(repo, f"{EXAMS}/2025-06.solutions.md", SOLUTIONS.format(status="verified", extra=""))
    rep = run(repo, f"{EXAMS}/2025-06.solutions.md")
    assert any("verified_by" in e for e in rep.errors)
    assert any("verified_on" in e for e in rep.errors)


def test_verified_with_fields_ok(repo):
    w(repo, f"{EXAMS}/2025-06.md", SESSION.format(sol="verified"))
    extra = "verified_by: nikos\nverified_on: 2026-10-07\n"
    w(repo, f"{EXAMS}/2025-06.solutions.md", SOLUTIONS.format(status="verified", extra=extra))
    rep = run(repo, f"{EXAMS}/2025-06.solutions.md")
    assert not any("verified_" in e for e in rep.errors)
    assert not any("Previous Exams" in e for e in rep.errors), rep.errors


def test_verified_bad_date(repo):
    w(repo, f"{EXAMS}/2025-06.md", SESSION.format(sol="verified"))
    extra = "verified_by: nikos\nverified_on: '07/10/2026'\n"
    w(repo, f"{EXAMS}/2025-06.solutions.md", SOLUTIONS.format(status="verified", extra=extra))
    assert any("YYYY-MM-DD" in e for e in run(repo, f"{EXAMS}/2025-06.solutions.md").errors)


def test_exam_validator_error_surfaces(repo):
    w(repo, f"{EXAMS}/2025-06.md", "no frontmatter at all\n")
    rep = run(repo, f"{EXAMS}/2025-06.md")
    assert any("missing YAML frontmatter" in e for e in rep.errors)


def test_summary_markdown(repo):
    rep = run(repo, "tools/x.md")
    text = cc.summary_markdown(rep, 1)
    assert "❌" in text and "tools/x.md" in text
    assert "✅" in cc.summary_markdown(cc.Report(), 3)


def test_cli_files_exit_codes(repo, capsys):
    w(repo, "docs/ok.md", "# fine\n")
    assert cc.main(["--root", str(repo), "--files", "docs/ok.md"]) == 0
    w(repo, "docs/bad.md", "6912345678\n")
    assert cc.main(["--root", str(repo), "--files", "docs/bad.md"]) == 1


def test_changed_files_from_git(repo):
    import subprocess
    def g(*a):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=repo, check=True,
                       capture_output=True)
    g("init", "-q", "-b", "main")
    g("add", "-A"); g("commit", "-q", "-m", "base")
    g("checkout", "-q", "-b", "pr")
    w(repo, "docs/Νέο αρχείο.md", "# x\n")
    (repo / f"{EXAMS}/README.md").unlink()
    g("add", "-A"); g("commit", "-q", "-m", "pr")
    ch = {(c.status, c.path) for c in cc.changed_files("main", repo)}
    assert ("A", "docs/Νέο αρχείο.md") in ch and ("D", f"{EXAMS}/README.md") in ch
