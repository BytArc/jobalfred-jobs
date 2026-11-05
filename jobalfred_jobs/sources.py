"""Fetchers for official public job-board APIs. Each returns normalised Job objects.

Sources are limited to APIs the vendors publish for reading public postings:
  Greenhouse Job Board API, Lever Postings API, Ashby public job posting API.
LinkedIn, Indeed and Naukri are never used. Workday, SmartRecruiters, Workable and
Recruitee are left out on purpose: see README, "Sources".
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards"
LEVER = "https://api.lever.co/v0/postings"
LEVER_EU = "https://api.eu.lever.co/v0/postings"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board"

# Not real roles: evergreen forms that collect CVs.
NOT_A_ROLE = re.compile(
    r"talent\s+(pool|community|network|pipeline)|general\s+application|open\s+application|"
    r"spontaneous|speculative|future\s+(opportunit|opening|role)|don.?t\s+see|stay\s+in\s+touch|"
    r"join\s+our\s+talent|expression\s+of\s+interest",
    re.I,
)


class BoardGone(Exception):
    """The API answered 404: the board moved or closed."""


class BoardError(Exception):
    """A temporary failure. The board's rows must not be treated as closed."""


@dataclass
class Job:
    source: str
    token: str
    job_id: str
    company: str
    title: str
    url: str
    posted: str
    posted_kind: str
    locations: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    remote: bool = False
    text: str = ""  # transient: used for sponsorship matching, never written to disk

    @property
    def id(self) -> str:
        return f"{self.source}-{self.token}-{self.job_id}".lower()

    @property
    def location(self) -> str:
        seen, out = set(), []
        for loc in self.locations:
            key = loc.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(loc.strip())
        return "; ".join(out)


_BLOCK = re.compile(r"</?(p|div|li|ul|ol|br|h[1-6]|tr|td|section|article|blockquote)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(raw: str | None) -> str:
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _BLOCK.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def _day(value) -> str:
    if value in (None, ""):
        return ""
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, OverflowError, OSError):
        return ""


def _check(status: int, what: str) -> None:
    if status == 200:
        return
    if status == 404:
        raise BoardGone(what)
    raise BoardError(f"{what}: HTTP {status}")


def greenhouse(client, token: str, company: str, want_text: bool) -> list[Job]:
    params = {"content": "true"} if want_text else None
    status, data = client.get_json(f"{GREENHOUSE}/{token}/jobs", params)
    _check(status, f"greenhouse/{token}")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    jobs = []
    for j in (data or {}).get("jobs", []):
        title = (j.get("title") or "").strip()
        url = j.get("absolute_url") or ""
        if not title or not url or NOT_A_ROLE.search(title):
            continue
        deadline = _day(j.get("application_deadline"))
        if deadline and deadline < today:
            continue
        locs = [((j.get("location") or {}).get("name") or "").strip()]
        for office in j.get("offices") or []:
            locs.append((office.get("location") or office.get("name") or "").strip())
        posted = _day(j.get("first_published"))
        kind = "first_published"
        if not posted:
            posted, kind = _day(j.get("updated_at")), "updated"
        text = html_to_text(j.get("content")) if want_text else ""
        joined = " ".join(locs).lower()
        jobs.append(Job("greenhouse", token, str(j.get("id")), company, title, url, posted, kind,
                        [l for l in locs if l], [], "remote" in joined, text))
    return jobs


def _lever_text(j: dict) -> str:
    parts = [j.get("descriptionPlain") or ""]
    for block in j.get("lists") or []:
        parts.append(block.get("text") or "")
        parts.append(html_to_text(block.get("content")))
    parts.append(j.get("additionalPlain") or "")
    return "\n".join(p for p in parts if p)


def lever(client, token: str, company: str, want_text: bool, eu: bool = False) -> list[Job]:
    base = LEVER_EU if eu else LEVER
    source = "lever-eu" if eu else "lever"
    status, data = client.get_json(f"{base}/{token}", {"mode": "json"})
    _check(status, f"{source}/{token}")
    jobs = []
    for j in data or []:
        title = (j.get("text") or "").strip()
        url = j.get("hostedUrl") or ""
        if not title or not url or NOT_A_ROLE.search(title):
            continue
        cats = j.get("categories") or {}
        locs = [cats.get("location") or ""] + list(cats.get("allLocations") or [])
        country = (j.get("country") or "").upper()
        remote = (j.get("workplaceType") or "").lower() == "remote"
        jobs.append(Job(source, token, str(j.get("id")), company, title, url, _day(j.get("createdAt")),
                        "created", [l for l in locs if l], [country] if country else [], remote,
                        _lever_text(j) if want_text else ""))
    return jobs


def ashby(client, token: str, company: str, want_text: bool) -> list[Job]:
    status, data = client.get_json(f"{ASHBY}/{token}")
    _check(status, f"ashby/{token}")
    jobs = []
    for j in (data or {}).get("jobs", []):
        if j.get("isListed") is False:  # Ashby: unlisted jobs are for direct links only
            continue
        title = (j.get("title") or "").strip()
        url = j.get("jobUrl") or ""
        if not title or not url or NOT_A_ROLE.search(title):
            continue
        locs, countries = [j.get("location") or ""], []
        def add_country(addr):
            c = ((addr or {}).get("postalAddress") or {}).get("addressCountry")
            if c:
                countries.append(c)
        add_country(j.get("address"))
        for sec in j.get("secondaryLocations") or []:
            locs.append(sec.get("location") or "")
            add_country(sec.get("address"))
        remote = (j.get("workplaceType") or "").lower() == "remote"
        jobs.append(Job("ashby", token, str(j.get("id")), company, title, url, _day(j.get("publishedAt")),
                        "published", [l for l in locs if l], countries, remote,
                        (j.get("descriptionPlain") or "") if want_text else ""))
    return jobs


def fetch(client, company: dict, want_text: bool) -> list[Job]:
    ats, token, name = company["ats"], company["token"], company["name"]
    if ats == "greenhouse":
        return greenhouse(client, token, name, want_text)
    if ats == "lever":
        return lever(client, token, name, want_text)
    if ats == "lever-eu":
        return lever(client, token, name, want_text, eu=True)
    if ats == "ashby":
        return ashby(client, token, name, want_text)
    raise ValueError(f"unknown ats: {ats}")
