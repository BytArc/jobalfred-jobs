"""Verify board tokens against the live APIs and report what each board really holds.

A board counts as verified only when its API answers and the board belongs to the company:
  greenhouse: the API's own board name matches the company name;
  lever, ashby: these APIs return no board name, so the company name must appear in the
  postings themselves.
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import classify, sources
from .http import PoliteClient


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def tokens_for(name: str, extra: list[str]) -> list[str]:
    base = re.sub(r"\(.*?\)", "", name).strip()
    plain = norm(base)
    dashed = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return list(dict.fromkeys([*extra, plain, dashed]))


def identity_greenhouse(client, token: str, name: str) -> str | None:
    status, data = client.get_json(f"{sources.GREENHOUSE}/{token}")
    if status != 200:
        return None
    board = (data or {}).get("name") or ""
    a, b = norm(board), norm(re.sub(r"\(.*?\)", "", name))
    return board if a and b and (a in b or b in a) else None


def identity_text(jobs, name: str) -> bool:
    needle = re.sub(r"\(.*?\)", "", name).strip().lower()
    return any(needle in (j.text or "").lower() for j in jobs)


def summarise(jobs) -> dict:
    return {
        "open": len(jobs),
        "india": sum(classify.in_india(j) for j in jobs),
        "portugal": sum(classify.in_portugal(j) for j in jobs),
        "remote_eu": sum(classify.remote_eu_scope(j) is not None for j in jobs),
        "eu": sum(classify.eu_location(j) is not None for j in jobs),
        "sample": [{"t": j.title, "l": j.location, "u": j.url} for j in jobs[:2]],
    }


def probe(client, ats: str, cand: dict) -> list[dict]:
    hits = []
    for token in tokens_for(cand["name"], cand.get("tokens", [])):
        company = {"ats": ats, "token": token, "name": cand["name"]}
        try:
            jobs = sources.fetch(client, company, want_text=True)
        except (sources.BoardGone, sources.BoardError):
            continue
        if not jobs:
            continue
        if ats == "greenhouse":
            board = identity_greenhouse(client, token, cand["name"])
            how = f"board name: {board}" if board else None
        else:
            how = "name in postings" if identity_text(jobs, cand["name"]) else None
        hits.append({**cand, "ats": ats, "token": token, "identity": how, **summarise(jobs)})
        break
    return hits


def main(path: str, out: str) -> None:
    candidates = json.load(open(path))
    client = PoliteClient(retries=1)
    results: list[dict] = []

    def run(ats: str):
        for i, cand in enumerate(candidates):
            for hit in probe(client, ats, cand):
                results.append(hit)
                print(f"{ats:10} {hit['token']:24} {hit['name']:28} open={hit['open']:<5} "
                      f"in={hit['india']:<4} pt={hit['portugal']:<4} rem={hit['remote_eu']:<4} eu={hit['eu']:<4} "
                      f"id={hit['identity']}", flush=True)
            if i % 50 == 0:
                print(f"# {ats} {i}/{len(candidates)}", file=sys.stderr, flush=True)
            json.dump({"at": datetime.now(timezone.utc).isoformat(), "results": results}, open(out, "w"))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, ["greenhouse", "lever", "lever-eu", "ashby"]))
    json.dump({"at": datetime.now(timezone.utc).isoformat(), "results": results}, open(out, "w"), indent=1)
    print(f"done: {len(results)} boards, {client.requests_made} requests")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
