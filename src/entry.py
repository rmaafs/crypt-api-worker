from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

from src.handlers import handle_create_message, handle_get_message
from src.rate_limiter import RateLimiter
from src.utils import error_response, CORS_HEADERS


class Default(WorkerEntrypoint):
    # Rate limiter is per-isolate instance (not per-request).
    # NOTE: In Cloudflare Workers, each isolate has its own RateLimiter,
    # so this is NOT globally consistent across all edge locations.
    rate_limiter = RateLimiter()

    async def fetch(self, request):
        try:
            return await self._handle_request(request)
        except Exception:
            # Global catch: never leak internal details
            return error_response("Internal server error", 500)

    async def _handle_request(self, request):
        method = request.method
        path = urlparse(request.url).path

        # OPTIONS preflight — always allow, no rate limit check
        if method == "OPTIONS":
            return self._preflight_response()

        # Rate limit check
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()
        )

        # Configure rate limiter from env if available
        rate_limit = int(getattr(self.env, "RATE_LIMIT_PER_SECOND", 3))
        self.rate_limiter.max_requests_per_second = rate_limit

        if not self.rate_limiter.is_allowed(client_ip):
            return error_response("Rate limit exceeded", 429)

        # Route: POST /
        if path == "/":
            if method != "POST":
                return error_response("Method not allowed", 405)
            return await handle_create_message(request, self.env)

        # Route: GET /{id} — any path with a single segment
        segments = [s for s in path.split("/") if s]
        if len(segments) == 1:
            if method != "GET":
                return error_response("Method not allowed", 405)
            return await handle_get_message(segments[0], self.env)

        # No matching route
        return error_response("Not found", 404)

    @staticmethod
    def _preflight_response():
        """Return a 204 preflight CORS response."""
        return Response(None, status=204, headers=CORS_HEADERS)
