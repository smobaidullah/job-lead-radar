"""Fetchers for free public job-board APIs, normalised to one Job shape.

Each source's terms ask for a credit and a link back to the original listing,
so every Job keeps its source name and original URL, and the report shows both.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import requests

USER_AGENT = "job-lead-radar/1.0 (+https://github.com/smobaidullah/job-lead-radar)"
TIMEOUT = 30


@dataclass
class Job:
    source: str
    id: str
    title: str
    company: str
    url: str
    posted: datetime
    location: str = ""
    tags: list[str] = field(default_factory=list)
    salary: str = ""
    description: str = ""
    score: int = 0
    matched: list[str] = field(default_factory=list)
    is_new: bool = False

    @property
    def key(self) -> str:
        """Identity used to spot the same job posted on more than one board."""
        norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
        return f"{norm(self.company)}|{norm(self.title)}"


# UTF-8 bytes that were decoded as Windows-1252/Latin-1 ("Ã©" instead of "é",
# "â€™" instead of "’"). Remote OK's API returns some text like this.
_CP1252_EXTRA = "€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ"
_MOJIBAKE = re.compile(rf"[Â-ô][\u0080-¿{_CP1252_EXTRA}]{{1,3}}")


def _undo_mojibake(match: re.Match) -> str:
    chunk = match.group(0)
    try:
        raw = bytes(ord(c) if ord(c) < 256 else c.encode("cp1252")[0] for c in chunk)
        return raw.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return chunk  # not actually mojibake; leave it alone


def fix_mojibake(text: str) -> str:
    return _MOJIBAKE.sub(_undo_mojibake, text or "")


def strip_html(text: str) -> str:
    text = fix_mojibake(text)
    text = re.sub(r"<(br|/p|/li|/h\d)\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t ]+", " ", html.unescape(text))
    lines = (line.strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def _get(url: str):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _salary(lo, hi) -> str:
    lo, hi = int(lo or 0), int(hi or 0)
    if lo and hi:
        return f"${lo:,} - ${hi:,}"
    return f"${(lo or hi):,}" if (lo or hi) else ""


def fetch_remoteok() -> list[Job]:
    rows = _get("https://remoteok.com/api")
    jobs = []
    for r in rows:
        if "id" not in r:  # first element is the legal notice
            continue
        jobs.append(Job(
            source="Remote OK",
            id=str(r["id"]),
            title=fix_mojibake(r.get("position", "")).strip(),
            company=fix_mojibake(r.get("company", "")).strip(),
            url=r.get("url") or f"https://remoteok.com/remote-jobs/{r['id']}",
            posted=datetime.fromisoformat(r["date"]),
            location=r.get("location") or "Remote",
            tags=[t.lower() for t in r.get("tags", [])],
            salary=_salary(r.get("salary_min"), r.get("salary_max")),
            description=strip_html(r.get("description", "")),
        ))
    return jobs


def fetch_remotive() -> list[Job]:
    data = _get("https://remotive.com/api/remote-jobs?category=software-dev")
    return [
        Job(
            source="Remotive",
            id=str(r["id"]),
            title=r["title"].strip(),
            company=r["company_name"].strip(),
            url=r["url"],
            posted=datetime.fromisoformat(r["publication_date"]).replace(tzinfo=timezone.utc),
            location=r.get("candidate_required_location") or "Remote",
            tags=[t.lower() for t in r.get("tags", [])],
            salary=r.get("salary") or "",
            description=strip_html(r.get("description", "")),
        )
        for r in data.get("jobs", [])
    ]


def fetch_arbeitnow() -> list[Job]:
    data = _get("https://www.arbeitnow.com/api/job-board-api")
    return [
        Job(
            source="Arbeitnow",
            id=r["slug"],
            title=r["title"].strip(),
            company=r["company_name"].strip(),
            url=r["url"],
            posted=datetime.fromtimestamp(r["created_at"], tz=timezone.utc),
            location=("Remote" if r.get("remote") else r.get("location", "")),
            tags=[t.lower() for t in r.get("tags", [])],
            description=strip_html(r.get("description", "")),
        )
        for r in data.get("data", [])
        if r.get("remote")  # this board is mostly on-site in Germany; keep remote roles only
    ]


SOURCES: dict[str, Callable[[], list[Job]]] = {
    "remoteok": fetch_remoteok,
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
}
