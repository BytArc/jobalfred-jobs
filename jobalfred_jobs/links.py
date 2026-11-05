"""Link building. One UTM scheme, defined in release-kit/growth/MEASUREMENT.md.

Apply links go straight to the employer: the same URL, no redirect, no tracking.
Install links go to jobalfred.com/go in `go` mode, or straight to the Chrome Web Store in `store` mode.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def add_params(url: str, params: dict) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in params]
    query.extend((k, v) for k, v in params.items() if v not in (None, ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def is_web_url(url: str) -> bool:
    parts = urlsplit(url or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def apply_link(url: str, campaign: str, channel: str = "github") -> str:
    """Employer link, unchanged. No tracking parameters: an employer's system could record them as the
    candidate's source, and the applicant should not carry our campaign into their application."""
    return url


def install_link(settings: dict, list_slug: str, campaign: str, job_id: str = "", source: str = "github") -> str:
    """Install link. utm_source names the channel, because the channel is the referrer here."""
    utm = {"utm_source": source, "utm_medium": "job_list", "utm_campaign": campaign, "utm_content": job_id}
    if settings.get("install_mode") == "store":
        return add_params(settings["store_url"], utm)
    return add_params(settings["site"].rstrip("/") + "/go/", {"list": list_slug, "job": job_id, **utm})
