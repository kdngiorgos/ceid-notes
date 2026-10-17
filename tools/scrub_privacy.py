"""Privacy patterns for the public CEID Notes repository (regex part only).

This is a stripped copy of the master repo's ``scrub_privacy.py``: it contains only the static detection
patterns and ``find_pii``. It has NO mapping/username loading code and never reads any secret file.
It reports *where* a match is, never the matched text itself.
"""
from __future__ import annotations
import re

_CDN_URL = re.compile(r"https://(?:cdn|media)\.discordapp\.(?:com|net)/attachments/(?:[^/\s]+/)+([^/\s?)]+)(?:\?[^\s)]*)?")
_EMAIL_STUDENT = re.compile(r"\b(?:up|st)?\d{4,8}@(?:upnet\.gr|ac\.upatras\.gr|ceid\.upatras\.gr)\b", re.I)
_EMAIL_PERSONAL = re.compile(
    r"[\w.+%-]{1,64}@(?:gmail\.com|(?:yahoo|hotmail|outlook|windowslive|live|msn|icloud)\.[a-z]+(?:\.[a-z]+)*)", re.I)
_STUDENT_ID = re.compile(r"\b(?:up|st)\d{7}\b", re.I)
# AM label: Greek A.M. / AM with any spacing, optional ":" or "=", then 6-7 digits; Latin AM only with ":" or "=".
_AM_LABEL = re.compile(r"(?i)\b(?:Α\s{0,3}\.?\s{0,3}Μ\s{0,3}\.?\s{0,3}[:=]?|A\.?M\.?\s{0,3}[:=])\s{0,3}\d{6,7}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?30[\s-]?)?69\d{8}(?!\d)")
# Discord user ids; zero-width characters were sometimes inserted into mentions.
_ZW = "[​-‍﻿]*"
_USER_MENTION = re.compile(rf"<{_ZW}@{_ZW}!?{_ZW}(\d{{15,20}}){_ZW}>")
_DISCORD_ID_LABELLED = re.compile(r"(?i)\b(?:discord[\s_-]*)?(?:user[\s_-]*)?id\b\s*[:=]\s*\d{17,20}\b")

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Discord attachment URL", _CDN_URL),
    ("student e-mail", _EMAIL_STUDENT),
    ("personal e-mail", _EMAIL_PERSONAL),
    ("student ID (up/st + 7 digits)", _STUDENT_ID),
    ("AM (registration number) label", _AM_LABEL),
    ("phone number", _PHONE),
    ("Discord user mention", _USER_MENTION),
    ("Discord user id", _DISCORD_ID_LABELLED),
]


def find_pii(text: str) -> list[tuple[int, str]]:
    """Return ``[(1-based line number, description)]`` for every privacy match in ``text``."""
    hits: list[tuple[int, str]] = []
    for n, line in enumerate(text.split("\n"), 1):
        for what, rx in PATTERNS:
            if rx.search(line):
                hits.append((n, what))
    return hits
