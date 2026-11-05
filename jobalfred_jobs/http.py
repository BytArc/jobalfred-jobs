"""A small polite HTTP client: one request at a time per host, with backoff."""
from __future__ import annotations

import threading
import time
from urllib.parse import urlsplit

import requests

USER_AGENT = "JobAlfredJobsBot/0.1 (+https://github.com/BytArc/jobalfred-jobs)"

# Seconds between requests to one host. api.lever.co publishes Crawl-delay: 1.
# The others publish no limit, so we stay at the same conservative pace.
MIN_INTERVAL = {
    "boards-api.greenhouse.io": 0.5,
    "api.lever.co": 1.0,
    "api.eu.lever.co": 1.0,
    "api.ashbyhq.com": 1.0,
}
DEFAULT_INTERVAL = 1.0
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_BACKOFF = 60.0


class PoliteClient:
    def __init__(self, timeout: float = 45.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self._locks: dict[str, threading.Lock] = {}
        self._last: dict[str, float] = {}
        self._guard = threading.Lock()
        self.requests_made = 0

    def _wait(self, host: str) -> None:
        with self._guard:
            lock = self._locks.setdefault(host, threading.Lock())
        with lock:
            gap = MIN_INTERVAL.get(host, DEFAULT_INTERVAL)
            delay = self._last.get(host, 0.0) + gap - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()

    def get_json(self, url: str, params: dict | None = None):
        """Return (status, parsed JSON or None). Never raises on HTTP errors."""
        host = urlsplit(url).hostname or ""
        status = 0
        for attempt in range(self.retries + 1):
            self._wait(host)
            self.requests_made += 1
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                status = 0
                time.sleep(min(2 ** attempt, MAX_BACKOFF))
                continue
            status = resp.status_code
            if status == 200:
                try:
                    return status, resp.json()
                except ValueError:
                    return 0, None
            if status not in RETRY_STATUS:
                return status, None
            retry_after = resp.headers.get("Retry-After", "")
            wait = float(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
            time.sleep(min(wait, MAX_BACKOFF))
        return status, None
