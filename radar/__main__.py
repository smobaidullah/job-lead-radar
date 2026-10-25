"""Run with:  python -m radar [--config config.toml] [--out site] [--previous URL_OR_PATH]"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tomllib
from pathlib import Path

import requests

from .report import write_excel, write_html, write_json
from .scoring import rank
from .sources import SOURCES, Job

log = logging.getLogger("radar")


def load_previous_ids(location: str | None) -> set[str] | None:
    """IDs from the last published leads.json, so we can flag what's new.

    Returns None when there is no previous run (first run: nothing is marked new).
    """
    if not location:
        return None
    try:
        if location.startswith("http"):
            resp = requests.get(location, timeout=20)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            payload = resp.json()
        else:
            path = Path(location)
            if not path.exists():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
    except (requests.RequestException, ValueError) as exc:
        log.warning("could not read previous run (%s); nothing will be marked new", exc)
        return None
    return {f"{j['source']}:{j['id']}" for j in payload.get("jobs", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Collect and rank remote dev job leads.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--out", default="site", help="output folder")
    parser.add_argument("--previous", help="URL or path of the previous leads.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    config = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))

    jobs: list[Job] = []
    for name, fetch in SOURCES.items():
        try:
            found = fetch()
            log.info("%-10s %4d jobs", name, len(found))
            jobs.extend(found)
        except (requests.RequestException, ValueError, KeyError) as exc:
            # one board being down shouldn't stop the whole report
            log.warning("%-10s failed: %s", name, exc)

    if not jobs:
        log.error("every source failed; leaving the previous report in place")
        return 1

    ranked = rank(jobs, config)
    previous = load_previous_ids(args.previous)
    if previous is not None:
        for job in ranked:
            job.is_new = f"{job.source}:{job.id}" not in previous

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_json(ranked, out / "leads.json")
    write_excel(ranked, out / "leads.xlsx")
    write_html(ranked, out / "index.html")
    log.info("kept %d of %d jobs (%d new) -> %s", len(ranked), len(jobs), sum(j.is_new for j in ranked), out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
