"""Bounded failed-login protection using direct peer and exact username.

Exact limits: 10 failures per account and 50 per direct peer in a rolling
300-second window. An attempt at the exact expiry boundary is admitted.
In-flight attempts reserve capacity atomically and count until completion or
window expiry. Success or an infrastructure exception removes only its own
reservation; neither erases previous failures. Rejections never extend TTL.
At most 8192 buckets are retained, with at most 50 events in any bucket.
Expired events are cleaned lazily on each admission. Capacity exhaustion
rejects new identities until space expires; active protection is never evicted.

shortcut: state is single-process and lost on restart; before multiple workers
or replicas, require separately reviewed shared enforcement. No distributed
or proxy-authentication guarantees are provided. ASGI client identity must be
the direct transport peer, not rewritten from untrusted forwarded headers.
"""

import hashlib
import ipaddress
import math
import threading
import time

ACCOUNT_FAILURES = 10
IP_FAILURES = 50
WINDOW_SECONDS = 300
MAX_BUCKETS = 8192


class FailedLoginLimiter:
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets = {}

    def reserve(self, username, address):
        if address is None:
            address = "<missing-direct-peer>"
        else:
            try:
                address = str(ipaddress.ip_address(address))
            except ValueError:
                pass
        # Fixed-size digests prevent retained state growing with input length.
        keys = (
            (
                "account",
                hashlib.sha256(
                    username.encode("utf-8", errors="surrogatepass")
                ).digest(),
            ),
            (
                "ip",
                hashlib.sha256(
                    address.encode("utf-8", errors="surrogatepass")
                ).digest(),
            ),
        )
        with self._lock:
            now = self._clock()
            cutoff = now - WINDOW_SECONDS
            for key, events in list(self._buckets.items()):
                remaining = [event for event in events if event[0] > cutoff]
                if remaining:
                    self._buckets[key] = remaining
                else:
                    del self._buckets[key]
            waits = []
            for key, limit in zip(keys, (ACCOUNT_FAILURES, IP_FAILURES)):
                events = self._buckets.get(key, ())
                if len(events) >= limit:
                    waits.append(events[0][0] + WINDOW_SECONDS - now)
            if waits:
                return None, max(1, math.ceil(max(waits)))
            missing = sum(key not in self._buckets for key in keys)
            if len(self._buckets) + missing > MAX_BUCKETS:
                wait = (
                    min(events[0][0] for events in self._buckets.values())
                    + WINDOW_SECONDS
                    - now
                )
                return None, max(1, math.ceil(wait))
            marker = object()
            for key in keys:
                self._buckets.setdefault(key, []).append((now, marker))
            return (keys, marker), 0

    def complete(self, ticket, *, failed):
        if failed:
            return
        keys, marker = ticket
        with self._lock:
            for key in keys:
                events = self._buckets.get(key)
                if events is None:
                    continue
                remaining = [event for event in events if event[1] is not marker]
                if remaining:
                    self._buckets[key] = remaining
                else:
                    del self._buckets[key]
