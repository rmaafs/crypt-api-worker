import time


class RateLimiter:
    """Sliding window rate limiter per IP address.

    NOTE: This rate limiter is per-isolate in Cloudflare Workers.
    Each Worker isolate maintains its own in-memory state, so rate
    limiting is NOT globally consistent across multiple isolates.
    This provides best-effort protection but is not a hard guarantee.
    """

    def __init__(self, max_requests_per_second=3):
        self.max_requests_per_second = max_requests_per_second
        self._timestamps: dict[str, list[float]] = {}

    def is_allowed(self, ip: str) -> bool:
        """Check if the IP is allowed to make a request using sliding window."""
        now = time.time()
        window_start = now - 1.0

        # Get or create timestamps list for this IP
        timestamps = self._timestamps.get(ip, [])

        # Filter to only keep timestamps within the 1-second window
        timestamps = [ts for ts in timestamps if ts > window_start]

        if len(timestamps) >= self.max_requests_per_second:
            self._timestamps[ip] = timestamps
            return False

        timestamps.append(now)
        self._timestamps[ip] = timestamps

        # Periodically clean expired entries to avoid memory leaks
        self._cleanup(now)

        return True

    def _cleanup(self, now: float):
        """Remove expired timestamp entries to prevent memory leaks."""
        window_start = now - 1.0
        expired_ips = [
            ip
            for ip, timestamps in self._timestamps.items()
            if not timestamps or timestamps[-1] <= window_start
        ]
        for ip in expired_ips:
            del self._timestamps[ip]
