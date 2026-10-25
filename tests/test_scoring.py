from datetime import datetime, timedelta, timezone

from radar.scoring import dedupe, rank, score_job
from radar.sources import Job, strip_html

NOW = datetime(2026, 10, 25, tzinfo=timezone.utc)


def job(title, company="Acme", days_old=1, desc="", tags=(), source="Remotive", id_=None):
    return Job(
        source=source, id=id_ or title, title=title, company=company, url="https://example.com",
        posted=NOW - timedelta(days=days_old), tags=list(tags), description=desc,
    )


def test_title_beats_tags_beats_description():
    w = {"flutter": 6}
    assert score_job(job("Flutter Developer"), w).score == 12
    assert score_job(job("Mobile Developer", tags=["flutter"]), w).score == 6
    assert score_job(job("Mobile Developer", desc="We use Flutter."), w).score == 3


def test_keywords_need_word_boundaries():
    # "react" must not match "reactive", but "node.js" style terms still match
    j = score_job(job("Engineer", desc="Reactive streams with Node.js"), {"react": 3, "node.js": 2})
    assert j.matched == ["node.js"]


def test_penalties_count_in_title_but_not_description():
    w = {"react": 3, "senior": -3}
    assert score_job(job("Senior React Engineer"), w).score == 6 - 6
    assert score_job(job("React Engineer", desc="Pair with senior devs"), w).score == 6


def test_dedupe_keeps_newest_across_boards():
    old = job("React Dev", company="Acme Inc.", days_old=5, source="Remote OK", id_="1")
    new = job("React dev", company="acme inc", days_old=1, source="Remotive", id_="2")
    assert [j.id for j in dedupe([old, new])] == ["2"]


def test_rank_filters_age_exclusions_and_min_score():
    config = {
        "keywords": {"react": 3},
        "min_score": 3,
        "max_age_days": 7,
        "exclude_titles": ["sales"],
    }
    jobs = [
        job("React Developer"),                    # kept
        job("React Developer II", days_old=30),    # too old
        job("Sales Engineer (React)"),             # excluded title
        job("Backend Developer"),                  # no match
    ]
    assert [j.title for j in rank(jobs, config, now=NOW)] == ["React Developer"]


def test_strip_html():
    assert strip_html("<p>Hello&nbsp;<b>there</b></p><p>Line 2</p>") == "Hello there\nLine 2"
