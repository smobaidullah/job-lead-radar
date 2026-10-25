# Job Lead Radar

Every morning this collects remote developer jobs from three free job-board APIs, removes the duplicates, scores each one against a list of keywords, and publishes the results as a searchable web page and an Excel file. It runs on GitHub Actions and GitHub Pages, so it costs nothing to host.

**Live page:** https://smobaidullah.github.io/job-lead-radar/
**Excel download:** https://smobaidullah.github.io/job-lead-radar/leads.xlsx

## How it works

1. **Collect** (`radar/sources.py`): pulls listings from the Remote OK, Remotive and Arbeitnow public APIs and normalises them into one `Job` shape. If one board is down, the others still run.
2. **Clean and rank** (`radar/scoring.py`):
   - drops anything older than `max_age_days` and any title on the exclude list ("sales", "director" and so on)
   - de-duplicates the same company and title posted on more than one board
   - scores each keyword by where it shows up: in the title it counts double, in the tags it counts once, and in the description only it counts half. Long descriptions tend to name every technology, so they can't push a job to the top on their own. Penalties like "senior" only apply when they're in the title or tags.
3. **Spot what's new**: each run fetches the previous day's published `leads.json` and flags anything that wasn't there.
4. **Report** (`radar/report.py`): writes `leads.json`, a formatted Excel file (frozen header, filters, clickable links, new rows highlighted, a per-source summary sheet) and a static HTML page with live filtering.

All the tuning lives in `config.toml`, so changing what counts as a good lead means editing weights, not code.

## Run it yourself

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
python -m radar --out site    # then open site/index.html
python -m pytest              # tests for scoring, de-duplication and HTML cleaning
```

## Sources

Listings come from the public APIs of [Remote OK](https://remoteok.com), [Remotive](https://remotive.com) and [Arbeitnow](https://www.arbeitnow.com). As their terms ask, the page credits each one and every listing links back to its original post.
