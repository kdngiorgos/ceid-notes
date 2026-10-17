"""Mechanical quality gate for ``Previous Exams/`` (formats F2 transcripts, F3 sessions, F4 solutions).

Every error is one line: ``<path relative to the course folder>[:<line>]: <rule that failed>``.
The CLI prefixes the course path (``<course rel>: <error>``), prints nothing when everything is valid and
exits with 1 when there are errors.

CLI: ``validate_exams.py (--course REL | --all) [--transcripts-only] [--root PATH]``
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import argparse, os, re, unicodedata
from pathlib import Path

import yaml
import kb_common as kc

SESSION_NAME_RE = re.compile(r"^\d{4}(-\d{2})?(-[a-z0-9]+)?\.md$")
SESSION_HINT_RE = re.compile(r"^\d{4}(-\d{2})?$")
# Ruling R3: .md files whose name has one of these extensions before ".md" are sidecars / transcripts /
# solutions, not session files.
DOUBLE_EXTS = {"pdf", "docx", "pptx", "ppsx", "doc", "ppt", "xlsx", "jpg", "jpeg", "png", "webp", "heic",
               "transcript", "solutions"}
RESERVED_MD = {"README.md", "discord_recalls.md"}
LEGACY_NAME = "previous_exams.md"
# Public repo: exam originals (images/PDFs) are not published, so `sources` entries cannot be checked on disk.
WEB_EDITION = True

FORMATS = ("multiple-choice", "open", "mixed", "lab", "oral", "unknown")
TRANSCRIPTIONS = ("verbatim", "partial", "recalled")
SOLUTION_STATUSES = ("none", "official", "community", "ai-unverified", "verified")
LEGIBILITY = ("good", "partial", "poor")
TRANSCRIPT_DOCS = ("exam_paper", "exam_solution", "other")

_SOLUTION_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


# ---------------------------------------------------------------- shared helpers (also used by the other tools)

def _exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def _is_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def parse_markdown(path: Path) -> tuple[dict | None, str, int, str | None]:
    """Split a Markdown file into ``(frontmatter, body, first_body_line, error)``.

    ``frontmatter`` is None when the file has none (or it is not a YAML mapping, then ``error`` says why).
    ``first_body_line`` is the 1-based line number of the first body line, so callers can report file lines.
    Tolerates a BOM and CRLF newlines.
    """
    return parse_text(path.read_text(encoding="utf-8-sig"))


def parse_text(text: str) -> tuple[dict | None, str, int, str | None]:
    """Same as :func:`parse_markdown` for text that is already in memory."""
    text = text.replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        tail = 5
        if end == -1 and text.endswith("\n---"):
            end, tail = len(text) - 4, 4
        if end != -1:
            raw = text[4:end + 1] if end >= 4 else ""
            body = text[end + tail:]
            first_line = text.count("\n", 0, end + tail) + 1
            try:
                meta = yaml.safe_load(raw)
            except yaml.YAMLError as e:
                first = str(e).strip().splitlines()[0] if str(e).strip() else "parse error"
                return None, body, first_line, f"frontmatter is not valid YAML ({first})"
            if meta is None:
                meta = {}
            if not isinstance(meta, dict):
                return None, body, first_line, "frontmatter is not a YAML mapping (key: value pairs)"
            return meta, body, first_line, None
    return None, text, 1, None


def is_aux_md(name: str) -> bool:
    """True for ``.md`` files in ``Previous Exams/`` that are NOT session files (Ruling R3 + reserved names)."""
    if name in RESERVED_MD:
        return True
    if not name.lower().endswith(".md"):
        return True
    stem = name[:-3]
    _, dot, ext = stem.rpartition(".")
    return bool(dot) and ext.lower() in DOUBLE_EXTS


def list_session_files(exams_dir: Path) -> list[Path]:
    """Session files that follow the naming pattern, sorted by name (``previous_exams.md`` is not one)."""
    try:
        names = sorted(p.name for p in exams_dir.iterdir() if p.is_file())
    except OSError:
        return []
    return [exams_dir / n for n in names
            if not is_aux_md(n) and n != LEGACY_NAME and SESSION_NAME_RE.match(n)]


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", t).replace("ς", "σ")


# "Λύση" / "Λύσεις" / "Solution(s)" as a word start, accents and case ignored ("Επίλυση" and "Ανάλυση" do not match).
_SOLUTION_WORD_RE = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(_norm(w)) for w in ("Λύση", "Λύσεις", "Solution")) + ")")


def _course_code(course_dir: Path) -> tuple[str | None, list[str]]:
    _, code_raw = kc.split_course_dirname(course_dir.name)
    if not code_raw:
        return None, []
    return kc.normalize_code(code_raw), kc.code_aliases(code_raw)


def _course_matches(value, code: str | None, aliases: list[str]) -> bool:
    if code is None:
        return True
    s = str(value).strip()
    return kc.normalize_code(s) == code or s in aliases


_JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _source_key(name: str) -> str:
    """Comparison key for a `sources` entry / file name: forward slashes, no leading ./, case-insensitive."""
    return os.path.normpath(name.strip()).replace("\\", "/").casefold()


def _is_nonempty_str(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _one_of(v, allowed) -> bool:
    return isinstance(v, str) and v in allowed


# ---------------------------------------------------------------- F3 / F4: sessions and solutions

def _check_session_frontmatter(meta: dict, rel: str, stem: str, exams_dir: Path,
                               code: str | None, aliases: list[str]) -> list[str]:
    errs: list[str] = []
    for key in ("course", "session", "label", "sources", "format", "transcription", "solutions"):
        if meta.get(key) in (None, "", []):
            errs.append(f"{rel}: frontmatter key '{key}' is missing or empty (required by format F3)")
    if "course" in meta and meta["course"] is not None and not _course_matches(meta["course"], code, aliases):
        errs.append(f"{rel}: frontmatter 'course' = {meta['course']!r} does not match this course folder ({code})")
    if meta.get("session") is not None and str(meta["session"]) != stem:
        errs.append(f"{rel}: frontmatter 'session' = {meta['session']!r} must equal the file name stem {stem!r}")
    if "label" in meta and meta["label"] is not None and not _is_nonempty_str(meta["label"]):
        errs.append(f"{rel}: frontmatter 'label' must be a non-empty string")
    if meta.get("format") is not None and not _one_of(meta["format"], FORMATS):
        errs.append(f"{rel}: frontmatter 'format' = {meta['format']!r} is not one of: {', '.join(FORMATS)}")
    if meta.get("transcription") is not None and not _one_of(meta["transcription"], TRANSCRIPTIONS):
        errs.append(f"{rel}: frontmatter 'transcription' = {meta['transcription']!r} is not one of: "
                    f"{', '.join(TRANSCRIPTIONS)}")
    if meta.get("solutions") is not None and not _one_of(meta["solutions"], SOLUTION_STATUSES):
        errs.append(f"{rel}: frontmatter 'solutions' = {meta['solutions']!r} is not one of: "
                    f"{', '.join(SOLUTION_STATUSES)}")
    dm = meta.get("duration_min")
    if dm is not None and (isinstance(dm, bool) or not isinstance(dm, (int, float)) or dm <= 0):
        errs.append(f"{rel}: frontmatter 'duration_min' must be a positive number of minutes or null, got {dm!r}")
    if meta.get("notes") is not None and not isinstance(meta["notes"], str):
        errs.append(f"{rel}: frontmatter 'notes' must be a string or null, got {meta['notes']!r}")
    sources = meta.get("sources")
    if "sources" in meta and sources is not None:
        if not isinstance(sources, list) or not sources:
            errs.append(f"{rel}: frontmatter 'sources' must be a non-empty list of files relative to Previous Exams/")
        else:
            for s in sources:
                if not _is_nonempty_str(s):
                    errs.append(f"{rel}: frontmatter 'sources' contains an invalid entry: {s!r}")
                elif not WEB_EDITION and not _exists(exams_dir / s):
                    errs.append(f"{rel}: source not found: {s}")
    return errs


def _solution_heading_errors(body: str, first_line: int, rel: str, stem: str) -> list[str]:
    errs: list[str] = []
    in_fence = False
    for i, line in enumerate(body.split("\n")):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _SOLUTION_HEADING_RE.match(line)
        if m and _SOLUTION_WORD_RE.search(_norm(m.group(1))):
            errs.append(f"{rel}:{first_line + i}: solution heading in a session file ({line.strip()!r}); "
                        f"solutions belong in {stem}.solutions.md, the session file holds the exam text only")
    return errs


def _check_solutions_file(path: Path, rel: str, stem: str, code: str | None, aliases: list[str]) -> tuple[list[str], str | None]:
    """Validate an F4 file. Returns ``(errors, status)``."""
    errs: list[str] = []
    try:
        meta, body, _, err = parse_markdown(path)
    except (OSError, UnicodeDecodeError) as e:
        return [f"{rel}: cannot read file ({e})"], None
    if err:
        return [f"{rel}: {err}"], None
    if meta is None:
        return [f"{rel}: missing YAML frontmatter (required by format F4: course, session, status, source)"], None
    for key in ("course", "session", "status", "source"):
        if meta.get(key) in (None, ""):
            errs.append(f"{rel}: frontmatter key '{key}' is missing or empty (required by format F4)")
    if meta.get("course") not in (None, "") and not _course_matches(meta["course"], code, aliases):
        errs.append(f"{rel}: frontmatter 'course' = {meta['course']!r} does not match this course folder ({code})")
    if meta.get("session") not in (None, "") and str(meta["session"]) != stem:
        errs.append(f"{rel}: frontmatter 'session' = {meta['session']!r} must equal {stem!r}")
    status = meta.get("status")
    if status not in (None, "") and not _one_of(status, [s for s in SOLUTION_STATUSES if s != "none"]):
        errs.append(f"{rel}: frontmatter 'status' = {status!r} is not one of: "
                    f"{', '.join(s for s in SOLUTION_STATUSES if s != 'none')}")
    if meta.get("source") not in (None, "") and not _is_nonempty_str(meta["source"]):
        errs.append(f"{rel}: frontmatter 'source' must be a string saying where the solutions came from")
    w = meta.get("warnings")
    if w is not None and not (isinstance(w, list) and all(_is_nonempty_str(x) for x in w)):
        errs.append(f"{rel}: frontmatter 'warnings' must be a list of non-empty strings")
    if not body.strip():
        errs.append(f"{rel}: empty body (the solutions must mirror the numbering of {stem}.md)")
    return errs, status if isinstance(status, str) else None


def validate_exams(course_dir: Path) -> list[str]:
    """Check ``<course>/Previous Exams``; returns error strings (empty list = valid)."""
    exams = course_dir / "Previous Exams"
    if not _is_dir(exams):
        return []
    errs: list[str] = []
    code, aliases = _course_code(course_dir)
    if _exists(exams / LEGACY_NAME):
        errs.append(f"Previous Exams/{LEGACY_NAME}: legacy aggregate file must be deleted "
                    f"(split it into per-session files <YYYY-MM>.md and <YYYY-MM>.solutions.md)")
    try:
        entries = sorted(p for p in exams.iterdir() if p.is_file())
    except OSError as e:
        return errs + [f"Previous Exams: cannot list folder ({e})"]
    names = {p.name for p in entries}

    session_stems: set[str] = set()
    listed: set[str] = set()          # every file named in some session's `sources` (normalized)
    sources_known = True              # False when a session file could not be read: skip the unlisted-source check
    for p in entries:
        name = p.name
        if name == LEGACY_NAME or is_aux_md(name):
            continue
        rel = f"Previous Exams/{name}"
        if not SESSION_NAME_RE.match(name):
            errs.append(f"{rel}: file name does not match the session pattern YYYY[-MM][-suffix].md "
                        f"(lowercase letters/digits only, e.g. 2025-06.md, 2025-06-a.md, 2019.md); "
                        f"sidecars are named <original>.<ext>.md, transcripts <original>.transcript.md")
            continue
        stem = name[:-3]
        session_stems.add(stem)
        try:
            meta, body, first_line, err = parse_markdown(p)
        except (OSError, UnicodeDecodeError) as e:
            errs.append(f"{rel}: cannot read file ({e})")
            sources_known = False
            continue
        if err:
            errs.append(f"{rel}: {err}")
            sources_known = False
            continue
        if meta is None:
            errs.append(f"{rel}: missing YAML frontmatter (format F3: course, session, label, sources, "
                        f"format, transcription, solutions)")
            sources_known = False
            continue
        if isinstance(meta.get("sources"), list):
            listed.update(_source_key(x) for x in meta["sources"] if isinstance(x, str))
        else:
            sources_known = False
        errs.extend(_check_session_frontmatter(meta, rel, stem, exams, code, aliases))
        errs.extend(_solution_heading_errors(body, first_line, rel, stem))
        if not any(ln.strip() and not ln.lstrip().startswith("#") for ln in body.split("\n")):
            errs.append(f"{rel}: the body has no exam text (only headings or nothing); "
                        f"an empty template is not a transcription")
        status = meta.get("solutions")
        sol_name = f"{stem}.solutions.md"
        if isinstance(status, str) and status in SOLUTION_STATUSES:
            if status != "none":
                if sol_name not in names:
                    errs.append(f"{rel}: frontmatter 'solutions' is {status!r} but {sol_name} does not exist "
                                f"(create it with status {status!r}, or set 'solutions: none')")
                else:
                    sol_errs, sol_status = _check_solutions_file(exams / sol_name, f"Previous Exams/{sol_name}",
                                                                 stem, code, aliases)
                    errs.extend(sol_errs)
                    if sol_status is not None and sol_status != status:
                        errs.append(f"Previous Exams/{sol_name}: frontmatter 'status' = {sol_status!r} does not match "
                                    f"'solutions: {status}' in {name}")
            elif sol_name in names:
                errs.append(f"{rel}: frontmatter says 'solutions: none' but {sol_name} exists "
                            f"(set 'solutions' to the status in {sol_name})")

    if sources_known:                                          # exam originals that no session lists in `sources`
        for p in entries:
            if p.name.lower().endswith(".md") or p.name in _JUNK_FILES:
                continue                                       # .md = sessions, sidecars, transcripts, README, ...
            if _source_key(p.name) not in listed:
                errs.append(f"Previous Exams/{p.name}: unlisted source: {p.name} (no session lists it in 'sources'; "
                            f"add it to the session it belongs to, or move it to other/ if it is not exam material)")

    for p in entries:                                          # solutions files without a session
        if p.name.endswith(".solutions.md") and p.name[:-len(".solutions.md")] not in session_stems:
            errs.append(f"Previous Exams/{p.name}: no matching session file {p.name[:-len('.solutions.md')]}.md")

    readme = exams / "README.md"
    if "README.md" not in names:
        errs.append("Previous Exams/README.md: missing; generate it with "
                    "tools/render_readmes.py --course <course> --only sessions")
    else:
        try:
            text = readme.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as e:
            errs.append(f"Previous Exams/README.md: cannot read file ({e})")
        else:
            b, e_ = text.find("<!-- BEGIN:sessions -->"), text.find("<!-- END:sessions -->")
            if b == -1 or e_ == -1 or e_ < b:
                errs.append("Previous Exams/README.md: missing the generated region "
                            "<!-- BEGIN:sessions --> ... <!-- END:sessions --> "
                            "(run tools/render_readmes.py --course <course> --only sessions)")
    return errs


# ---------------------------------------------------------------- F2: vision transcripts

def validate_transcripts(course_dir: Path) -> list[str]:
    """Check every ``*.transcript.md`` anywhere under the course folder against format F2."""
    errs: list[str] = []
    for dirpath, dirnames, filenames in os.walk(course_dir, onerror=lambda e: None):
        dirnames[:] = sorted(d for d in dirnames if d not in kc.SKIP_DIRS)
        for fn in sorted(filenames):
            if not fn.endswith(".transcript.md"):
                continue
            path = Path(dirpath) / fn
            try:
                rel = path.relative_to(course_dir).as_posix()
            except ValueError:
                rel = str(path)
            errs.extend(_check_transcript(path, rel, fn))
    return errs


def _check_transcript(path: Path, rel: str, fn: str) -> list[str]:
    errs: list[str] = []
    try:
        meta, body, _, err = parse_markdown(path)
    except (OSError, UnicodeDecodeError) as e:
        return [f"{rel}: cannot read transcript ({e})"]
    if err:
        return [f"{rel}: {err}"]
    if meta is None:
        return [f"{rel}: missing YAML frontmatter (format F2: source, kind, transcriber, legibility, doc)"]
    for key in ("source", "kind", "transcriber", "legibility", "doc"):
        if meta.get(key) in (None, ""):
            errs.append(f"{rel}: frontmatter key '{key}' is missing or empty (required by format F2)")
    if meta.get("kind") not in (None, "") and meta["kind"] != "transcript":
        errs.append(f"{rel}: frontmatter 'kind' must be 'transcript', got {meta['kind']!r}")
    src = meta.get("source")
    if src not in (None, ""):
        if not _is_nonempty_str(src) or "/" in str(src) or "\\" in str(src):
            errs.append(f"{rel}: frontmatter 'source' must be the bare file name of the original in the same folder")
        else:
            if not _exists(path.parent / src):
                errs.append(f"{rel}: source file not found next to the transcript: {src}")
            if fn != f"{src}.transcript.md":
                errs.append(f"{rel}: file name must be '{src}.transcript.md' (<original file name>.transcript.md)")
    tr = meta.get("transcriber")
    if tr not in (None, "") and (not _is_nonempty_str(tr) or "|" in str(tr)):
        errs.append(f"{rel}: frontmatter 'transcriber' must name one model (e.g. gemini-3.8-flash or "
                    f"claude-sonnet), got {tr!r}")
    if meta.get("legibility") not in (None, "") and not _one_of(meta["legibility"], LEGIBILITY):
        errs.append(f"{rel}: frontmatter 'legibility' = {meta['legibility']!r} is not one of: {', '.join(LEGIBILITY)}")
    if meta.get("doc") not in (None, "") and not _one_of(meta["doc"], TRANSCRIPT_DOCS):
        errs.append(f"{rel}: frontmatter 'doc' = {meta['doc']!r} is not one of: {', '.join(TRANSCRIPT_DOCS)}")
    for key in ("course_hint", "page_hint"):
        v = meta.get(key)
        if v is not None and not isinstance(v, (str, int)):
            errs.append(f"{rel}: frontmatter {key!r} must be a string or null")
    sh = meta.get("session_hint")
    if sh is not None and not SESSION_HINT_RE.match(str(sh)):
        errs.append(f"{rel}: frontmatter 'session_hint' = {sh!r} must be YYYY-MM, YYYY or null")
    if not body.strip():
        errs.append(f"{rel}: empty transcript body")
    return errs


# ---------------------------------------------------------------- CLI

def _select_courses(args, root: Path, ap: argparse.ArgumentParser):
    courses = kc.iter_courses(root)
    if args.all:
        return courses
    by_rel = {c.rel: c for c in courses}
    picked = []
    for rel in args.course:
        key = rel.replace("\\", "/").strip("/")
        if key not in by_rel:
            ap.error(f"unknown course (use the path relative to the root): {rel}")
        picked.append(by_rel[key])
    return picked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate Previous Exams folders (F2 transcripts, F3 sessions, F4 solutions).")
    ap.add_argument("--course", action="append", default=[], metavar="REL")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--transcripts-only", action="store_true", help="only check *.transcript.md files (format F2)")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    if not (args.all or args.course):
        ap.error("give --all or --course REL")
    root = Path(args.root).resolve() if args.root else kc.ROOT
    bad_courses = n_errors = 0
    for c in _select_courses(args, root, ap):
        errs: list[str] = []
        try:
            if not args.transcripts_only:
                errs.extend(validate_exams(c.path))
            errs.extend(validate_transcripts(c.path))
        except OSError as e:
            errs.append(f"cannot read course folder ({e})")
        for e in errs:
            print(f"{c.rel}: {e}")
        n_errors += len(errs)
        bad_courses += bool(errs)
    if n_errors:
        print(f"{n_errors} error(s) in {bad_courses} course(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
