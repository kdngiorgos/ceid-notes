"""Mechanical quality gate for course guides (format F6) and department guides (``guides/*.md``).

Error lines look like ``README.md:23: <rule that failed>`` (course guides, relative to the course folder)
or ``guides/choosing-electives.md:23: <rule>`` (department guides). The CLI prefixes course errors with the
course path (``<course rel>: <error>``), prints nothing when everything is valid and exits 1 on errors.

CLI: ``validate_guides.py (--course REL | --all | --dept)... [--root PATH]``
"""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import argparse, datetime as _dt, re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import kb_common as kc
from validate_exams import parse_text, _course_code, _course_matches, _exists

FULL_SECTIONS = ["Με μια ματιά", "Τι θα μάθεις", "Πώς βαθμολογείται", "Εργασίες & εργαστήρια", "Εξετάσεις",
                 "Δυσκολίες & παγίδες", "Υλικό & τρόπος μελέτης", "Συχνές ερωτήσεις", "Πηγές & αξιοπιστία"]
OLD_SECTIONS = ["Με μια ματιά", "Τι θα μάθεις", "Αντιστοιχία με νέο πρόγραμμα", "Εξετάσεις",
                "Υλικό & τρόπος μελέτης", "Πηγές & αξιοπιστία"]
COMMUNITY_SECTIONS = ["Τι θα βρεις εδώ", "Χρήσιμες πληροφορίες", "Συχνές ερωτήσεις", "Πηγές & αξιοπιστία"]
SECTIONS = {"core": FULL_SECTIONS, "elective": FULL_SECTIONS, "general-education": FULL_SECTIONS,
            "postgraduate": FULL_SECTIONS, "old-curriculum": OLD_SECTIONS,
            "community": COMMUNITY_SECTIONS, "topic": COMMUNITY_SECTIONS}
CITATION_SECTIONS = ("Πώς βαθμολογείται", "Δυσκολίες & παγίδες")
REQUIRED_KEYS = ("code", "title", "category", "sources", "last_reviewed")
# Department guides that are indexes/generated tables rather than claims: exempt from the citation rule.
DEPT_CITATION_EXEMPT = {"README.md", "curriculum-map.md"}
# Ruling (coordinator, A7 review): in department guides the intro section and the sources section are
# exempt from the citation rule; every other section is checked. (The blockquote under the H1 is never checked.)
DEPT_UNCITED_SECTIONS = ("Τι θα βρεις εδώ", "Πηγές & αξιοπιστία")

CITATION_RE = re.compile(r"\[(Discord|eClass|Κατάλογος|Εξετάσεις)[^\]]*\]\([^)]+\)")
NO_INFO = "Δεν βρέθηκαν πληροφορίες."
PII_PATTERNS = [
    (re.compile(r"\b(?:up|st)\d{7}\b", re.I), "student ID pattern (up/st + 7 digits)"),
    (re.compile(r"\b69\d{8}\b"), "phone number pattern (69 + 8 digits)"),
    (re.compile(r"cdn\.discordapp\.com/attachments"), "Discord CDN attachment URL"),
]
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_REGION_BEGIN_RE = re.compile(r"^\s*<!-- BEGIN:([\w-]+) -->\s*$")
_REGION_END_RE = re.compile(r"^\s*<!-- END:([\w-]+) -->\s*$")
_H2_RE = re.compile(r"^## (?!#)\s*(.*?)\s*#*\s*$")
_LINK_RE = re.compile(r"\]\(([^)\n]*)\)")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+:")
_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_BULLET_RE = re.compile(r"^(\s*)(?:[-*+]|\d{1,3}[.)])\s+(.*)$")
_SEPARATOR_ROW_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clip(s: str, n: int = 90) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


@dataclass
class _Item:
    line: int
    text: str
    kind: str            # bullet | para | row
    indent: int = 0
    has_child: bool = False


# ---------------------------------------------------------------- Markdown scanning helpers

def _split_regions(lines: list[str], first_line: int) -> tuple[list[tuple[int, str]], dict[str, tuple[int, int]]]:
    """Return ``(lines outside generated regions, {region name: (begin line, end line)})``.

    Lines are ``(file line number, text)``. Regions that are begun but never ended run to the end of the file.
    """
    outside: list[tuple[int, str]] = []
    regions: dict[str, tuple[int, int]] = {}
    open_name: str | None = None
    open_line = 0
    for i, line in enumerate(lines):
        ln = first_line + i
        mb, me = _REGION_BEGIN_RE.match(line), _REGION_END_RE.match(line)
        if open_name is None and mb:
            open_name, open_line = mb.group(1), ln
            continue
        if open_name is not None:
            if me and me.group(1) == open_name:
                regions.setdefault(open_name, (open_line, ln))
                open_name = None
            continue
        outside.append((ln, line))
    return outside, regions


def _h2_positions(lines: list[tuple[int, str]]) -> list[tuple[int, str, int]]:
    """``(line number, title, index into lines)`` for every H2 heading outside code fences."""
    out, in_fence = [], False
    for idx, (ln, line) in enumerate(lines):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _H2_RE.match(line)
        if m:
            out.append((ln, m.group(1), idx))
    return out


def _parse_items(lines: list[tuple[int, str]]) -> list[_Item]:
    """Split a section into the claims that need a citation: leaf bullets, paragraphs and table rows."""
    items: list[_Item] = []
    cur: _Item | None = None
    in_fence = in_table = False
    blank = True
    tbl_pos = 0
    for ln, raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if _FENCE_RE.match(line):
            in_fence, cur = not in_fence, None
            continue
        if in_fence:
            continue
        if not stripped:
            blank, in_table = True, False
            continue
        if re.match(r"^#{3,6}\s", stripped):                   # sub-headings are not claims
            cur, blank, in_table = None, False, False
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        mb = _BULLET_RE.match(line)
        if mb:
            indent = len(mb.group(1).expandtabs(4))
            for prev in reversed(items):                       # the nearest shallower bullet is the parent
                if prev.kind != "bullet":
                    break
                if prev.indent < indent:
                    prev.has_child = True
                    break
            cur = _Item(ln, mb.group(2).strip(), "bullet", indent)
            items.append(cur)
            blank, in_table = False, False
            continue
        if stripped.startswith("|"):
            if not in_table:
                in_table, tbl_pos = True, 0
            tbl_pos += 1
            cur = None
            blank = False
            if _SEPARATOR_ROW_RE.match(stripped):
                if tbl_pos == 2 and items and items[-1].kind == "row":
                    items.pop()                                # the row above the separator was the header
                continue
            items.append(_Item(ln, stripped, "row"))
            continue
        indent = len(line) - len(line.lstrip())
        if cur is not None and (not blank or (cur.kind == "bullet" and indent > cur.indent)):
            cur.text += " " + stripped                         # continuation line
        else:
            cur = _Item(ln, stripped, "para")
            items.append(cur)
        blank, in_table = False, False
    return items


def _mask_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans (keeps line structure) before scanning for links."""
    out, in_fence = [], False
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else re.sub(r"`[^`]*`", lambda m: " " * len(m.group()), line))
    return "\n".join(out)


def _link_errors(text: str, base_dir: Path, label: str, first_line: int = 1) -> list[str]:
    """``file:///`` links and relative links that do not resolve."""
    errs: list[str] = []
    for i, line in enumerate(_mask_code(text).split("\n")):
        ln = first_line + i
        for m in _LINK_RE.finditer(line):
            dest = m.group(1).strip()
            if not dest:
                continue
            if dest.lower().startswith(("file:", "<file:")):
                errs.append(f"{label}:{ln}: file:/// link found ({_clip(dest)}); use a relative link "
                            f"(tools/fix_links.py rewrites these)")
                continue
            if dest.startswith("<") and dest.endswith(">"):
                target = dest[1:-1]
            else:
                mt = re.match(r"""^(\S+)(?:\s+(?:"[^"]*"|'[^']*'))?$""", dest)
                if not mt:
                    errs.append(f"{label}:{ln}: link target has unencoded spaces/parentheses ({_clip(dest)}); "
                                f"encode them as %20/%28/%29 (kb_common.md_link_target)")
                    continue
                target = mt.group(1)
            if _DRIVE_RE.match(target):
                errs.append(f"{label}:{ln}: absolute Windows path used as a link ({_clip(target)}); use a relative link")
                continue
            if _SCHEME_RE.match(target) or target.startswith("#"):
                continue                                       # http(s), mailto, in-page anchors
            if target.startswith("/"):
                errs.append(f"{label}:{ln}: root-relative link ({_clip(target)}); use a path relative to this file")
                continue
            path_part = re.split(r"[#?]", target, maxsplit=1)[0]
            if not path_part:
                continue
            decoded = unquote(path_part)
            if not _exists(base_dir / decoded.rstrip("/")):
                errs.append(f"{label}:{ln}: broken relative link: {decoded} (target not found)")
    return errs


def _pii_errors(text: str, label: str) -> list[str]:
    errs: list[str] = []
    for i, line in enumerate(text.split("\n")):
        for rx, what in PII_PATTERNS:
            for m in rx.finditer(line):
                found = m.group()
                shown = found if "cdn." in found else found[:2] + "*" * (len(found) - 2)   # never echo the PII
                errs.append(f"{label}:{i + 1}: PII: {what} {shown!r}; remove it or replace it with a placeholder")
    return errs


# ---------------------------------------------------------------- the guide checks

def _frontmatter_errors(meta: dict, label: str, *, expected_category: str | None, folder_code,
                        aliases: list[str]) -> list[str]:
    errs: list[str] = []
    for k in REQUIRED_KEYS:
        if k not in meta:
            errs.append(f"{label}: frontmatter key '{k}' is missing (required: {', '.join(REQUIRED_KEYS)})")
    t = meta.get("title")
    if "title" in meta and not (isinstance(t, str) and t.strip()):
        errs.append(f"{label}: frontmatter 'title' must be a non-empty string")
    cat = meta.get("category")
    if "category" in meta:
        if not (isinstance(cat, str) and cat.strip()):
            errs.append(f"{label}: frontmatter 'category' must be a non-empty string")
        elif expected_category is not None:
            ok = cat == expected_category or {cat, expected_category} <= {"community", "topic"}
            if not ok:
                errs.append(f"{label}: frontmatter 'category' = {cat!r} but this course folder is {expected_category!r}")
    if "code" in meta and expected_category is not None:
        code = meta["code"]
        if code is not None and not isinstance(code, str):
            errs.append(f"{label}: frontmatter 'code' must be a string or null, got {code!r}")
        elif isinstance(code, str) and folder_code and not _course_matches(code, folder_code, aliases):
            errs.append(f"{label}: frontmatter 'code' = {code!r} does not match the course folder ({folder_code})")
        elif code is None and folder_code:
            errs.append(f"{label}: frontmatter 'code' is null but the folder name carries the code {folder_code}")
    if "sources" in meta and not isinstance(meta["sources"], (dict, list)):
        errs.append(f"{label}: frontmatter 'sources' must be a mapping or a list describing the sources used")
    lr = meta.get("last_reviewed")
    if "last_reviewed" in meta and not (isinstance(lr, (_dt.date, _dt.datetime))
                                        or (isinstance(lr, str) and _DATE_RE.match(lr))):
        errs.append(f"{label}: frontmatter 'last_reviewed' must be a date YYYY-MM-DD, got {lr!r}")
    d = meta.get("difficulty")
    if d is not None and (isinstance(d, bool) or not isinstance(d, int) or not 1 <= d <= 5):
        errs.append(f"{label}: frontmatter 'difficulty' must be an integer 1-5 or null, got {d!r}")
    for k in ("code_aliases", "instructors_2025_26", "prerequisites_recommended", "exam_sessions"):
        if meta.get(k) is not None and not isinstance(meta[k], list):
            errs.append(f"{label}: frontmatter {k!r} must be a list")
    return errs


def _validate_guide_file(path: Path, category: str, *, label: str, cite_all_sections: bool = False,
                         require_files_region: bool = True, check_citations: bool = True,
                         expected_category: str | None = None, folder_code=None,
                         aliases: list[str] | None = None) -> list[str]:
    if category not in SECTIONS:
        return [f"{label}: unknown category {category!r} (expected one of: {', '.join(sorted(SECTIONS))})"]
    try:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except FileNotFoundError:
        return [f"{label}: file is missing"]
    except (OSError, UnicodeDecodeError) as e:
        return [f"{label}: cannot read file ({e})"]
    errs: list[str] = []
    meta, body, first_line, err = parse_text(text)
    if err:
        errs.append(f"{label}: {err}")
    elif meta is None:
        errs.append(f"{label}: missing YAML frontmatter (required keys: {', '.join(REQUIRED_KEYS)})")
    else:
        errs.extend(_frontmatter_errors(meta, label, expected_category=expected_category,
                                        folder_code=folder_code, aliases=aliases or []))

    body_lines = body.split("\n")
    outside, regions = _split_regions(body_lines, first_line)

    # H1 title followed by the blockquote summary
    content = [(ln, t) for ln, t in outside if t.strip()]
    if not content or not re.match(r"^# (?!#)\S", content[0][1]):
        errs.append(f"{label}:{content[0][0] if content else first_line}: the body must start with the H1 title "
                    f"('# <title>') right after the frontmatter")
    elif len(content) < 2 or not re.match(r"^>\s*\S", content[1][1]):
        errs.append(f"{label}:{content[1][0] if len(content) > 1 else content[0][0]}: the H1 must be followed by a "
                    f"'> ' blockquote that says what the course is in 2-3 sentences")

    # H2 sections in order
    required = SECTIONS[category]
    h2s = _h2_positions(outside)
    titles = [t for _, t, _ in h2s]
    missing = [s for s in required if s not in titles]
    if missing:
        errs.append(f"{label}: missing section{'s' if len(missing) > 1 else ''} "
                    f"{', '.join(repr('## ' + m) for m in missing)} "
                    f"(a {category} guide needs these H2 sections, in order: {' | '.join(required)})")
    for s in required:
        lns = [ln for ln, t, _ in h2s if t == s]
        if len(lns) > 1:
            errs.append(f"{label}:{lns[1]}: section '## {s}' appears twice (first at line {lns[0]})")
    if not missing:
        first_seen = [t for t in dict.fromkeys(titles) if t in required]
        if first_seen != required:
            errs.append(f"{label}: sections are out of order; expected {' | '.join(required)} but found "
                        f"{' | '.join(first_seen)}")

    # citation rule
    if check_citations:
        cite_titles = ({t for t in titles if t not in DEPT_UNCITED_SECTIONS} if cite_all_sections
                      else {t for t in titles if t in CITATION_SECTIONS})
        for k, (ln, title, idx) in enumerate(h2s):
            if title not in cite_titles:
                continue
            end = h2s[k + 1][2] if k + 1 < len(h2s) else len(outside)
            items = [it for it in _parse_items(outside[idx + 1:end]) if not (it.kind == "bullet" and it.has_child)]
            if not items:
                errs.append(f"{label}:{ln}: section '{title}' is empty; add cited items or the sentence "
                            f"\"{NO_INFO}\"")
            for it in items:
                if not (CITATION_RE.search(it.text) or NO_INFO in it.text):
                    errs.append(f"{label}:{it.line}: section '{title}': {it.kind} has no citation link "
                                f"([Discord ...](...), [eClass ...](...), [Κατάλογος ...](...) or [Εξετάσεις ...](...)) "
                                f"and is not \"{NO_INFO}\": {_clip(it.text)!r}")

    # generated files region (last thing in a course guide)
    if require_files_region:
        reg = regions.get("files")
        if reg is None:
            errs.append(f"{label}: missing the generated region <!-- BEGIN:files --> ... <!-- END:files --> "
                        f"(run tools/render_readmes.py --course <course> --only files)")
        else:
            after = [(ln, t) for ln, t in outside if ln > reg[1] and t.strip()]
            if after:
                errs.append(f"{label}:{after[0][0]}: the files region must be the last thing in the guide "
                            f"(found text after <!-- END:files -->)")

    errs.extend(_link_errors(text, path.parent, label))
    errs.extend(_pii_errors(text, label))
    return errs


def validate_guide(course_dir: Path, category: str) -> list[str]:
    """Validate ``<course_dir>/README.md`` as a course guide (format F6) of the given category."""
    readme = course_dir / "README.md"
    if not _exists(readme):
        return ["README.md: missing; write the course guide (format F6)"]
    code, aliases = _course_code(course_dir)
    return _validate_guide_file(readme, category, label="README.md", expected_category=category,
                                folder_code=code, aliases=aliases)


def validate_dept_guide(path: Path, root: Path | None = None) -> list[str]:
    """Validate a department guide (``guides/*.md``): community sections, citations in every section except
    the intro (``Τι θα βρεις εδώ``) and ``Πηγές & αξιοπιστία``.

    ``guides/README.md`` and ``guides/curriculum-map.md`` are exempt from the citation rule altogether.
    """
    try:
        label = path.relative_to(root).as_posix() if root else f"guides/{path.name}"
    except ValueError:
        label = path.name
    return _validate_guide_file(path, "community", label=label, cite_all_sections=True,
                                require_files_region=False,
                                check_citations=path.name not in DEPT_CITATION_EXEMPT)


def validate_dept_guides(root: Path) -> list[str]:
    guides = root / "guides"
    if not guides.is_dir():
        return ["guides: folder does not exist (department guides are written in Wave D)"]
    errs: list[str] = []
    files = sorted(p for p in guides.glob("*.md") if p.is_file())
    if not files:
        errs.append("guides: no *.md files found")
    for p in files:
        errs.extend(validate_dept_guide(p, root))
    return errs


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate course guides (README.md, format F6) and department guides.")
    ap.add_argument("--course", action="append", default=[], metavar="REL")
    ap.add_argument("--all", action="store_true", help="every course folder")
    ap.add_argument("--dept", action="store_true", help="every guides/*.md department guide")
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    if not (args.all or args.course or args.dept):
        ap.error("give --all, --course REL or --dept")
    root = Path(args.root).resolve() if args.root else kc.ROOT
    lines: list[str] = []
    bad = 0
    if args.all or args.course:
        courses = kc.iter_courses(root)
        if not args.all:
            by_rel = {c.rel: c for c in courses}
            picked = []
            for rel in args.course:
                key = rel.replace("\\", "/").strip("/")
                if key not in by_rel:
                    ap.error(f"unknown course (use the path relative to the root): {rel}")
                picked.append(by_rel[key])
            courses = picked
        for c in courses:
            errs = validate_guide(c.path, c.category)
            lines.extend(f"{c.rel}: {e}" for e in errs)
            bad += bool(errs)
    if args.dept:
        errs = validate_dept_guides(root)
        lines.extend(errs)
        bad += bool(errs)
    for line in lines:
        print(line)
    if lines:
        print(f"{len(lines)} error(s) in {bad} guide set(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
