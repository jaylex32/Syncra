"""Shared HTTP session and rate limiting utilities."""

from __future__ import annotations

import threading
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RateLimiter:
    def __init__(self, rate_per_second: float = 1.0):
        self.interval = 1.0 / max(rate_per_second, 0.001)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                time.sleep(self._next_allowed - now)
            self._next_allowed = time.monotonic() + self.interval


class HttpClient:
    def __init__(self, user_agent: str, retries: int = 3, backoff: float = 0.5):
        self.session = requests.Session()
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
            backoff_factor=backoff,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({"User-Agent": user_agent})

    def get(self, url: str, *, timeout: int = 20, params: Optional[dict] = None) -> requests.Response:
        return self.session.get(url, timeout=timeout, params=params)
