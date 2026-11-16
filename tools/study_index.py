"""Build the homepage catalog from the same files MkDocs publishes."""

import json
import re
from pathlib import PurePosixPath
from urllib.parse import quote

from mkdocs.structure.files import File
from pymdownx.slugs import slugify
from yaml import safe_load


COURSE_FOLDERS = {"Semesters": "core", "Electives": "electives", "Old Classes": "old", "Postgraduate": "postgraduate"}
STUDY_HEADINGS = {"Τι θα μάθεις", "Υλικό & τρόπος μελέτης", "Δυσκολίες & παγίδες"}
SLUG = slugify(case="lower")


def metadata(file):
    text = file.content_string.lstrip("\ufeff")
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if match:
        return safe_load(match[1]) or {}, text[match.end():]
    return {}, text


def guide_sources(body, url):
    cleaned = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    introduction = re.search(r"^>\s+(.+)$", cleaned, re.M)
    sections = re.split(r"^## (.+)$", cleaned, flags=re.M)
    sources = []
    if introduction:
        sources.append({"title": "Σύνοψη μαθήματος", "url": url, "text": introduction[1]})
    for title, section in zip(sections[1::2], sections[2::2]):
        if title not in STUDY_HEADINGS:
            continue
        for paragraph in re.split(r"\n\s*\n", section.strip()):
            text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", paragraph)
            text = re.sub(r"[`*]", "", text)
            text = " ".join(text.split())
            if len(text) >= 50:
                sources.append({"title": title, "url": f"{url}#{quote(SLUG(title, '-'))}", "text": text})
    return sources


def on_files(files, *, config):
    courses = []
    exams = []
    pdf_page = files.get_file_from_path("study-guides.md")
    pdfs = {code: url for url, code in re.findall(
        r"\((https://github\.com/[^)\s]+/([^/)]+)\.pdf)\)", pdf_page.content_string
    )}
    for file in files.documentation_pages():
        parts = PurePosixPath(file.src_uri).parts
        category = COURSE_FOLDERS.get(parts[0].split(" (")[0])
        if category is None or len(parts) < 3 or parts[-1] != "README.md" or parts[-2] == "Previous Exams":
            continue
        meta, body = metadata(file)
        url = file.url
        code = meta.get("code", parts[-2])
        course = {
            "id": file.src_uri,
            "title": meta.get("title", parts[-2]),
            "code": code,
            "aliases": meta.get("code_aliases") or [],
            "category": category,
            "semester": meta.get("semester"),
            "ects": meta.get("ects"),
            "reviewed": str(meta.get("last_reviewed") or ""),
            "url": url,
            "pdf": pdfs.get(code),
            "sources": guide_sources(body, url),
            "examCount": 0,
        }
        courses.append(course)

    courses_by_dir = {PurePosixPath(course["id"]).parent: course for course in courses}
    for file in files.documentation_pages():
        path = PurePosixPath(file.src_uri)
        if path.parent.name != "Previous Exams" or not re.match(r"^\d", path.name) or path.name.endswith(".solutions.md"):
            continue
        course = courses_by_dir.get(path.parent.parent)
        if course is None:
            continue
        meta, _ = metadata(file)
        course["examCount"] += 1
        exams.append({
            "course": course["id"],
            "session": str(meta.get("session") or path.stem),
            "label": meta.get("label") or path.stem,
            "solutions": meta.get("solutions") or "unknown",
            "transcription": meta.get("transcription") or "unknown",
            "url": file.url,
        })

    index = {"courses": courses, "exams": exams, "pdfCount": len(pdfs)}
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    files.append(File.generated(config, "assets/study-index.js", content=f"const ceidStudyIndex = {payload};\n"))
