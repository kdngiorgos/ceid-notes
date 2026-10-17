"""Shared helpers for the CEID knowledge-base tools. Pure stdlib + PyYAML."""
from __future__ import annotations
import datetime as _dt, json, os, re, shutil, unicodedata
from dataclasses import dataclass, replace as _dc_replace
from pathlib import Path
from typing import Iterator
import yaml

ROOT = Path(__file__).resolve().parents[1]
CATEGORY_DIRS = {
    "core": "Semesters",
    "elective": "Electives (Μαθήματα Επιλογής)",
    "old-curriculum": "Old Classes (Παλαιό Πρόγραμμα Σπουδών)",
    "postgraduate": "Postgraduate (Μεταπτυχιακά)",
    "community": "General & Community (Κοινότητα & Πανεπιστήμιο)",
}
SEASON_DIRS = {"Χειμερινά (Winter-Fall)": "winter", "Εαρινά (Spring)": "spring",
               "Γενικής Παιδείας (General Education)": None}
SKIP_DIRS = {".git", ".venv", "_work", "discord_exporter", "__pycache__", "site", "node_modules"}

# Greek letters that look like Latin ones map to that Latin letter; the rest are transliterated.
_GR2LAT = {"Α": "A", "Β": "B", "Γ": "G", "Δ": "D", "Ε": "E", "Ζ": "Z", "Η": "H", "Θ": "TH", "Ι": "I",
           "Κ": "K", "Λ": "L", "Μ": "M", "Ν": "N", "Ξ": "KS", "Ο": "O", "Π": "P", "Ρ": "P", "Σ": "S",
           "Τ": "T", "Υ": "Y", "Φ": "F", "Χ": "X", "Ψ": "PS", "Ω": "O"}
_LAT2GR = {"A": "Α", "B": "Β", "E": "Ε", "Z": "Ζ", "H": "Η", "I": "Ι", "K": "Κ", "M": "Μ", "N": "Ν",
           "O": "Ο", "P": "Ρ", "T": "Τ", "Y": "Υ", "X": "Χ"}
_DIRNAME_RE = re.compile(r"^(?P<title>.*?)\s+-\s+(?P<code>CEID_?\S.*)$")

@dataclass(frozen=True)
class Course:
    path: Path
    rel: str
    category: str          # core|elective|general-education|old-curriculum|postgraduate|community
    title: str
    code_raw: str | None
    code: str | None
    semester: int | None
    season: str | None     # winter|spring|None
    slug: str

def normalize_code(code: str) -> str:
    s = unicodedata.normalize("NFC", code).replace(" ", "").upper()
    return "".join(_GR2LAT.get(ch, ch) for ch in s)

def code_aliases(code_raw: str) -> list[str]:
    ascii_ = normalize_code(code_raw)
    prefix, _, num = ascii_.partition("_") if "_" in ascii_ else ("", "", ascii_)
    greekish = "".join(_LAT2GR.get(ch, ch) for ch in num)
    out = [code_raw.replace(" ", ""), ascii_, num, greekish, f"CEID_{greekish}" if prefix else greekish]
    return list(dict.fromkeys(a for a in out if a))

def split_course_dirname(name: str) -> tuple[str, str | None]:
    m = _DIRNAME_RE.match(name)
    return (m.group("title").strip(), m.group("code").strip()) if m else (name.strip(), None)

def _slugify(text: str) -> str:
    t = "".join(_GR2LAT.get(ch.upper(), ch) for ch in unicodedata.normalize("NFD", text)
                if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "x"

def iter_courses(root: Path = ROOT) -> list[Course]:
    out: list[Course] = []
    def add(path: Path, category: str, semester=None, season=None):
        title, code_raw = split_course_dirname(path.name)
        code = normalize_code(code_raw) if code_raw else None
        slug = code or f"{'old' if category == 'old-curriculum' else category}-{_slugify(title)}"
        out.append(Course(path, path.relative_to(root).as_posix(), category, title, code_raw, code,
                          semester, season, slug))
    sem_dir = root / CATEGORY_DIRS["core"]
    for sem in sorted(p for p in sem_dir.glob("*") if p.is_dir()):
        m = re.match(r"Semester (\d+)", sem.name)
        for c in sorted(p for p in sem.iterdir() if p.is_dir()):
            add(c, "core", semester=int(m.group(1)) if m else None)
    el_dir = root / CATEGORY_DIRS["elective"]
    for grp in sorted(p for p in el_dir.glob("*") if p.is_dir()):
        season = SEASON_DIRS.get(grp.name)
        cat = "general-education" if "Γενικής Παιδείας" in grp.name else "elective"
        for c in sorted(p for p in grp.iterdir() if p.is_dir()):
            add(c, cat, season=season)
    for key in ("old-curriculum", "postgraduate", "community"):
        d = root / CATEGORY_DIRS[key]
        for c in sorted(p for p in d.glob("*") if p.is_dir()):
            add(c, key)
    return _unique_slugs(out)

def _unique_slugs(courses: list[Course]) -> list[Course]:
    """Make slugs unique: the first course (in iteration order) keeps its slug, later clashes get -2, -3, ..."""
    taken = {c.slug for c in courses}     # a suffixed slug must not hit a slug that already exists either
    seen: set[str] = set()
    out: list[Course] = []
    for c in courses:
        if c.slug in seen:
            n = 2
            while f"{c.slug}-{n}" in taken or f"{c.slug}-{n}" in seen:
                n += 1
            c = _dc_replace(c, slug=f"{c.slug}-{n}")
            taken.add(c.slug)
        seen.add(c.slug)
        out.append(c)
    return out

def _enc(part: str) -> str:
    return part.replace("%", "%25").replace(" ", "%20").replace("(", "%28").replace(")", "%29")

def md_link_target(from_file: Path, to_path: Path) -> str:
    rel = os.path.relpath(to_path, from_file.parent).replace(os.sep, "/")
    return "/".join(_enc(p) for p in rel.split("/"))

def read_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return (yaml.safe_load(text[4:end]) or {}), text[end + 5:]
    return {}, text

def write_frontmatter(path: Path, meta: dict, body: str) -> None:
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"---\n{fm}---\n{body}")

def replace_region(text: str, name: str, content: str) -> str:
    b, e = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
    block = f"{b}\n{content.rstrip(chr(10))}\n{e}"
    pat = re.compile(re.escape(b) + r".*?" + re.escape(e), re.S)
    if pat.search(text):
        return pat.sub(lambda _m: block, text, count=1)
    return text.rstrip("\n") + "\n\n" + block + "\n"

def _rel_or_abs(p: Path) -> str:
    try: return p.resolve().relative_to(ROOT).as_posix()
    except ValueError: return str(p)

def move_logged(src: Path, dst: Path, manifest: Path, reason: str, dry_run: bool = False) -> Path:
    final, n = dst, 2
    while final.exists():
        final = dst.with_name(f"{dst.stem} ({n}){dst.suffix}"); n += 1
    if dry_run:
        print(f"[dry-run] move {src} -> {final}")
        return final
    final.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(final))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                            "src": _rel_or_abs(src), "dst": _rel_or_abs(final), "reason": reason},
                           ensure_ascii=False) + "\n")
    return final

def academic_period(d: _dt.date) -> str:
    start = d.year if d.month >= 9 else d.year - 1
    half = "winter" if (d.month >= 9 or d.month <= 2) else "spring"
    return f"{start}-{str(start + 1)[2:]}_{half}"

def normalize_for_search(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", t).replace("ς", "σ")

def iter_files(root: Path, *, skip_dirs: set[str] = SKIP_DIRS) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: print(f"[warn] {e}")):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            yield Path(dirpath) / fn
