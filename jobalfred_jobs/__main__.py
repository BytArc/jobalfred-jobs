"""Refresh every list.  python -m jobalfred_jobs [--install-mode go|store] [--dry-run]"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import classify, links, render, sources
from .http import PoliteClient

ROOT = Path(__file__).resolve().parent.parent
MAX_FAILED_SHARE = 0.3    # above this, stop without writing, so an outage cannot empty the lists
CARRY_DAYS = 3            # keep a failing board's last rows this long, then treat them as closed


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8")) or {}


def previous(slug: str) -> list[dict]:
    path = ROOT / "data" / f"{slug}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("jobs", [])


def match(job: sources.Job, key: str) -> dict | None:
    """Return extra row fields when the role belongs on this list, else None."""
    if key == "india":
        return {} if classify.in_india(job) else None
    if key == "portugal":
        return {} if classify.in_portugal(job) else None
    if key == "remote_eu":
        scope = classify.remote_eu_scope(job)
        return {"scope": scope} if scope else None
    if key == "visa_eu":
        country = classify.eu_location(job)
        if not country:
            return None
        status, quote = classify.sponsorship(job.text, classify.eu_countries(job), classify.has_non_eu_location(job))
        if status == "stated":
            return {"country": country, "quote": tidy(quote)}
        if status in ("conditional", "elsewhere"):
            return {"country": country, "quote": tidy(quote), "status": status, "_conditional": True}
        return None
    raise ValueError(key)


def fetch_all(client: PoliteClient, companies: list[dict]):
    jobs, gone, failed = [], [], []
    groups: dict[str, list[dict]] = {}
    for company in companies:
        groups.setdefault(company["ats"], []).append(company)

    def run(group: list[dict]):
        for company in group:
            want_text = "visa_eu" in company.get("lists", [])
            try:
                for job in sources.fetch(client, company, want_text):
                    jobs.append((job, company))
            except sources.BoardGone:
                gone.append(company)
            except sources.BoardError:
                failed.append(company)

    with ThreadPoolExecutor(max_workers=len(groups) or 1) as pool:
        list(pool.map(run, groups.values()))
    return jobs, gone, failed


def tidy(text: str) -> str:
    """Plain hyphens and no pictographs, whatever the posting used."""
    text = re.sub(r"\s*[\u2012-\u2015]\s*", " - ", text)
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def build_rows(spec, jobs, settings, seen_before, today, oldest):
    rows, conditional, dedupe = [], [], set()
    for job, company in jobs:
        if spec["key"] not in company.get("lists", []) or not links.is_web_url(job.url):
            continue
        if job.posted and job.posted < oldest:  # usually an evergreen posting, not a live opening
            continue
        extra = match(job, spec["key"])
        if extra is None:
            continue
        key = (job.company.lower(), job.title.lower(), job.location.lower())
        if key in dedupe:
            continue
        dedupe.add(key)
        row = {
            "id": job.id, "company": tidy(job.company), "title": tidy(job.title), "location": tidy(job.location),
            "posted": job.posted, "posted_kind": job.posted_kind, "ats": job.source,
            "first_seen": seen_before.get(job.id, today), "url": job.url,
            "apply_url": links.apply_link(job.url, spec["campaign"]),
            "fill_url": links.install_link(settings, spec["slug"], spec["campaign"], job.id),
            **{k: v for k, v in extra.items() if not k.startswith("_")},
        }
        (conditional if extra.get("_conditional") else rows).append(row)
    return rows, conditional


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install-mode", choices=["go", "store"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    settings = load_yaml("settings.yml")
    if args.install_mode:
        settings["install_mode"] = args.install_mode
    catalog = load_yaml("companies.yml")
    companies = catalog["companies"]
    excluded = set((load_yaml("exclusions.yml").get("job_ids") or []))
    now = datetime.now(timezone.utc)
    today, built = now.strftime("%Y-%m-%d"), now.strftime("%d %b %Y, %H:%M UTC")

    client = PoliteClient()
    jobs, gone, failed = fetch_all(client, companies)
    jobs = [(j, c) for j, c in jobs if j.id not in excluded]
    if len(failed) > MAX_FAILED_SHARE * len(companies):
        print(f"ABORT: {len(failed)} of {len(companies)} boards failed. Nothing written.", file=sys.stderr)
        return 2

    if not args.dry_run:
        review = ROOT / ".review"
        review.mkdir(exist_ok=True)
        mentions = []
        for job, _ in jobs:
            if job.text and classify.eu_location(job):
                mentions += [{"company": job.company, "title": job.title, "location": job.location, "status": s, "quote": q}
                             for s, q, _ in classify.sponsorship_mentions(job.text)]
        render.write_json(review / "sponsorship-mentions.json", {"mentions": mentions})

    failed_keys = {(c["ats"], c["token"]) for c in failed}
    cutoff = (now - timedelta(days=CARRY_DAYS)).strftime("%Y-%m-%d")
    oldest = (now - timedelta(days=settings.get("max_age_days", 365))).strftime("%Y-%m-%d")
    run_lists, stats = [], {}
    for spec in settings["lists"]:
        old = previous(spec["slug"])
        rows, conditional = build_rows(spec, jobs, settings, {r["id"]: r.get("first_seen", today) for r in old}, today, oldest)
        new_ids = {r["id"] for r in rows}
        failed_prefixes = tuple(f"{a}-{t}-".lower() for a, t in failed_keys)
        carried = []
        for r in old:
            if r["id"] in new_ids or not failed_prefixes or not r["id"].startswith(failed_prefixes):
                continue
            since = r.get("stale_since", today)
            if since >= cutoff:  # keep it through a short outage, then treat the role as closed
                carried.append({**r, "stale_since": since})
        rows += carried
        rows.sort(key=lambda r: (r.get("posted") or "", r["company"].lower(), r["title"].lower()), reverse=True)
        stats[spec["slug"]] = {
            "open": len(rows), "added": len(new_ids - {r["id"] for r in old}),
            "removed_closed": len({r["id"] for r in old} - {r["id"] for r in rows}),
            "carried_after_fetch_error": len(carried),
            "companies": len({r["company"] for r in rows}),
        }
        if spec["key"] == "visa_eu":
            stats[spec["slug"]]["conditional_not_counted"] = len(conditional)
        print(spec["slug"], stats[spec["slug"]])
        if args.dry_run:
            run_lists.append({**spec, "count": len(rows)})
            continue
        payload = {"list": spec["slug"], "title": spec["title"], "built": now.isoformat(timespec="seconds"),
                   "count": len(rows), "licence": "CC-BY-4.0", "source_note": settings["source_note"]}
        if spec["key"] == "visa_eu":
            payload["disclaimer"] = render.DISCLAIMER
        payload["jobs"] = [render.public_record(r) for r in rows]
        render.write_json(ROOT / "data" / f"{spec['slug']}.json", payload)
        (ROOT / "lists" / f"{spec['slug']}.md").write_text(render.table_md(spec, rows, built, settings), encoding="utf-8")
        if spec["key"] == "visa_eu":
            review = ROOT / ".review"
            review.mkdir(exist_ok=True)
            render.write_json(review / "conditional-sponsorship.json", {"jobs": conditional})
        run_lists.append({**spec, "count": len(rows)})

    run = {"built": now.isoformat(timespec="seconds"), "boards": len(companies), "requests": client.requests_made,
           "boards_gone": [f"{c['ats']}/{c['token']}" for c in gone],
           "boards_failed": [f"{c['ats']}/{c['token']}" for c in failed], "lists": stats}
    print(json.dumps({k: run[k] for k in ("boards", "requests", "boards_gone", "boards_failed")}))
    if not args.dry_run:
        render.write_json(ROOT / "data" / "run.json", run)
        render.update_readme(ROOT / "README.md", render.readme_block(run_lists, built))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
