"""Keyword scoring, filtering and de-duplication."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .sources import Job


def _pattern(term: str) -> re.Pattern:
    # word boundaries, but allow terms like "c#", "next.js" and "node.js"
    return re.compile(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])")


def score_job(job: Job, weights: dict[str, int], title_bonus: int = 2) -> Job:
    """Score each keyword once, by where it shows up.

    Title: weight x title_bonus (penalties too, so "Senior ..." really sinks).
    Tags: full weight. Description only: half weight, and penalties are ignored
    there, since "you'll work with senior engineers" says nothing about the role.
    Long descriptions tend to name every technology, so they can't dominate.
    """
    title = job.title.lower()
    tags = " ".join(job.tags)
    desc = job.description.lower()
    score, matched = 0, []
    for term, weight in weights.items():
        pat = _pattern(term)
        if pat.search(title):
            score += weight * title_bonus
        elif pat.search(tags):
            score += weight
        elif weight > 0 and pat.search(desc):
            score += max(1, weight // 2)
        else:
            continue
        matched.append(term)
    job.score, job.matched = score, matched
    return job


def excluded(job: Job, exclude_titles: list[str]) -> bool:
    title = job.title.lower()
    return any(_pattern(t).search(title) for t in exclude_titles)


def dedupe(jobs: list[Job]) -> list[Job]:
    """Same company + title on several boards: keep the first one seen (the newest after sorting)."""
    seen: dict[str, Job] = {}
    for job in sorted(jobs, key=lambda j: j.posted, reverse=True):
        seen.setdefault(job.key, job)
    return list(seen.values())


def rank(jobs: list[Job], config: dict, now: datetime | None = None) -> list[Job]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=config.get("max_age_days", 14))
    weights = config["keywords"]
    kept = []
    for job in dedupe(jobs):
        if job.posted < cutoff or excluded(job, config.get("exclude_titles", [])):
            continue
        score_job(job, weights, config.get("title_bonus", 2))
        if job.score >= config.get("min_score", 1):
            kept.append(job)
    return sorted(kept, key=lambda j: (j.score, j.posted), reverse=True)
