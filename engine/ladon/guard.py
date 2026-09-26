"""Protecting the report endpoint: cleaning free text, pseudonymising reporters and rate limiting."""

import hashlib
import hmac
import re
import time
import unicodedata
from collections import defaultdict, deque

MAX_DESCRIPTION = 1000
_WHITESPACE = re.compile(r"\s+")


def clean_description(text: object) -> str:
    """Plain text only: control characters removed, whitespace collapsed, length capped.

    Stored as text and always escaped when shown, never rendered as HTML.
    """
    if not isinstance(text, str):
        return ""
    visible = "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t ")
    return _WHITESPACE.sub(" ", visible).strip()[:MAX_DESCRIPTION]


def reporter_key(client_ip: str, salt: str) -> str:
    """A keyed hash of the client IP, so reporters can be de-duplicated and rate limited without
    storing or logging the IP itself."""
    return hmac.new(salt.encode(), client_ip.encode(), hashlib.sha256).hexdigest()


class RateLimiter:
    def __init__(self, limit: int = 5, window_seconds: float = 600):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
