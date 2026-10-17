"""Automated checks for a pull request to CEID Notes (SPEC section 6).

Usage (from the repository root):
    python tools/check_contribution.py --base origin/main [--owner] [--summary-file out.md]
    python tools/check_contribution.py --files docs/Semesters/.../2025-06.md ...

Rules
  1. Files: contributors may only change ``docs/**`` files ending in ``.md`` or ``.yml``; no binaries, no
     symlinks, at most 200 KB per file, no deletions. Anything else (``.github``, ``tools``, ``mkdocs.yml``,
     ``docs/javascripts`` ...) is owner-only (``--owner`` lifts this).
  2. The exam and guide validators run for every touched course (docs/ mirrors the master layout).
  3. Privacy regexes (student IDs, phones, personal e-mails, Discord ids/CDN links); the match is never echoed.
  4. A solutions file with ``status: verified`` needs ``verified_by`` and ``verified_on: YYYY-MM-DD``.
Exit code 1 when there is any error. Warnings never fail the run.
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import argparse, datetime as _dt, subprocess
from dataclasses import dataclass, field
from pathlib import Path

import kb_common as kc
import validate_exams as ve
import validate_guides as vg
from scrub_privacy import find_pii

MAX_BYTES = 200 * 1024
ALLOWED_EXT = {".md", ".yml"}
DOCS = "docs"


@dataclass
class Change:
    status: str            # A, M, D, R ...
    path: str              # repo-relative, forward slashes


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------- git

def changed_files(base: str, root: Path) -> list[Change]:
    """Changes between ``base`` (merge-base) and HEAD."""
    out = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "--name-status", "-z", "--no-renames",
                          f"{base}...HEAD"], cwd=root, check=True, capture_output=True).stdout
    parts = out.decode("utf-8").split("\0")
    changes = []
    for i in range(0, len(parts) - 1, 2):
        changes.append(Change(parts[i][:1], parts[i + 1]))
    return changes


# ---------------------------------------------------------------- rules

def _file_rules(root: Path, c: Change, owner: bool, rep: Report) -> bool:
    """Returns True when the file should be content-checked."""
    p = c.path
    ext = Path(p).suffix.lower()
    in_docs = p.startswith(DOCS + "/")
    if c.status == "D":
        if not owner:
            rep.errors.append(f"{p}: deleting files is done by the maintainer only")
        return False
    if not owner:
        if not in_docs:
            rep.errors.append(f"{p}: only files under docs/ can be changed by contributors")
            return False
        if ext not in ALLOWED_EXT:
            rep.errors.append(f"{p}: file type {ext or '(none)'} is not allowed (only .md and .yml; no images/PDFs)")
            return False
    full = root / p
    if full.is_symlink():
        rep.errors.append(f"{p}: symbolic links are not allowed")
        return False
    if not full.is_file():
        rep.warnings.append(f"{p}: file not found in the working tree, skipped")
        return False
    size = full.stat().st_size
    if size > MAX_BYTES:
        rep.errors.append(f"{p}: {size // 1024} KB is over the 200 KB limit")
    raw = full.read_bytes()
    if b"\0" in raw:
        rep.errors.append(f"{p}: binary content is not allowed")
        return False
    return in_docs and ext in ALLOWED_EXT


def _privacy(root: Path, p: str, rep: Report) -> None:
    text = (root / p).read_text(encoding="utf-8", errors="replace")
    for ln, what in find_pii(text):
        rep.errors.append(f"{p}:{ln}: privacy: {what} (remove it or cover it)")


def _verified_rule(root: Path, p: str, rep: Report) -> None:
    if not p.endswith(".solutions.md"):
        return
    try:
        meta, _, _, err = ve.parse_markdown(root / p)
    except (OSError, UnicodeDecodeError) as e:
        rep.errors.append(f"{p}: cannot read file ({e})")
        return
    if err or meta is None:
        return                                    # the exam validator reports frontmatter problems
    if meta.get("status") != "verified":
        return
    by, on = meta.get("verified_by"), meta.get("verified_on")
    if not (isinstance(by, str) and by.strip()):
        rep.errors.append(f"{p}: status 'verified' needs a non-empty 'verified_by' (GitHub handle or nickname)")
    if isinstance(on, _dt.datetime):
        on = on.date()
    if isinstance(on, _dt.date):
        pass
    else:
        try:
            _dt.date.fromisoformat(str(on))
            if len(str(on)) != 10:
                raise ValueError
        except ValueError:
            rep.errors.append(f"{p}: status 'verified' needs 'verified_on: YYYY-MM-DD'")


def _course_of(path: Path, courses: dict[str, kc.Course], docs: Path) -> kc.Course | None:
    rel = path.relative_to(docs).as_posix()
    for crel, c in courses.items():
        if rel == crel or rel.startswith(crel + "/"):
            return c
    return None


def _validators(root: Path, md_files: list[str], rep: Report) -> None:
    docs = root / DOCS
    if not docs.is_dir():
        return
    courses = {c.rel: c for c in kc.iter_courses(docs)}
    touched: dict[str, kc.Course] = {}
    dept: list[Path] = []
    for p in md_files:
        full = root / p
        c = _course_of(full, courses, docs)
        if c:
            touched[c.rel] = c
        elif full.relative_to(docs).parts[:1] == ("guides",):
            dept.append(full)
    for rel, c in sorted(touched.items()):
        for e in ve.validate_exams(c.path):
            rep.errors.append(f"{DOCS}/{rel}/{e}")
        for e in vg.validate_guide(c.path, c.category):
            rep.errors.append(f"{DOCS}/{rel}/{e}")
        rep.checked.append(f"course: {c.title}")
    for path in sorted(dept):
        for e in vg.validate_dept_guide(path, docs):
            rep.errors.append(f"{DOCS}/{e}")
        rep.checked.append(f"guide: {path.name}")


def check(root: Path, changes: list[Change], owner: bool = False) -> Report:
    rep = Report()
    if not changes:
        rep.warnings.append("no changed files")
        return rep
    md_files: list[str] = []
    for c in changes:
        if not _file_rules(root, c, owner, rep):
            continue
        if Path(c.path).suffix.lower() == ".md":
            md_files.append(c.path)
        _privacy(root, c.path, rep)
        _verified_rule(root, c.path, rep)
    _validators(root, md_files, rep)
    return rep


# ---------------------------------------------------------------- output

def summary_markdown(rep: Report, n_files: int) -> str:
    if rep.ok:
        head = f"### Έλεγχος συνεισφοράς: ✅ πέρασε\n\nΕλέγχθηκαν {n_files} αρχεία."
    else:
        head = (f"### Έλεγχος συνεισφοράς: ❌ {len(rep.errors)} πρόβλημα(τα)\n\n"
                "Διόρθωσε τα παρακάτω και κάνε push ξανά· ο έλεγχος θα τρέξει αυτόματα.\n")
    body = ""
    if rep.errors:
        body += "\n".join(f"- `{e.split(': ', 1)[0]}`: {e.split(': ', 1)[1] if ': ' in e else ''}" for e in rep.errors[:100])
        if len(rep.errors) > 100:
            body += f"\n- … και άλλα {len(rep.errors) - 100}"
    if rep.warnings:
        body += "\n\nΠροειδοποιήσεις:\n" + "\n".join(f"- {w}" for w in rep.warnings)
    return head + ("\n" + body if body else "") + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check a CEID Notes pull request.")
    ap.add_argument("--root", default=".", help="repository root")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--base", help="git ref to diff against (e.g. origin/main)")
    g.add_argument("--files", nargs="+", help="explicit list of changed files (treated as added/modified)")
    ap.add_argument("--owner", action="store_true", help="the author is the maintainer: lift the owner-only rules")
    ap.add_argument("--summary-file", help="write the Markdown summary here")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    changes = changed_files(a.base, root) if a.base else [Change("M", f.replace("\\", "/")) for f in a.files]
    rep = check(root, changes, owner=a.owner)
    text = summary_markdown(rep, len(changes))
    if a.summary_file:
        Path(a.summary_file).write_text(text, encoding="utf-8", newline="\n")
    for e in rep.errors:
        print(f"ERROR {e}")
    for w in rep.warnings:
        print(f"warning {w}")
    if rep.ok:
        print(f"OK ({len(changes)} file(s))")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
