from urllib.parse import urlparse

from workers import Response, WorkerEntrypoint

from handlers import handle_create_message, handle_get_message
from rate_limiter import RateLimiter
from utils import error_response, CORS_HEADERS


class Default(WorkerEntrypoint):
    # Rate limiter is per-isolate instance (not per-request).
    # NOTE: In Cloudflare Workers, each isolate has its own RateLimiter,
    # so this is NOT globally consistent across all edge locations.
    rate_limiter = None

    def __init__(self, env, ctx):
        super().__init__(env, ctx)
        # Initialize rate limiter once per isolate with env config
        if Default.rate_limiter is None:
            rate_limit = int(getattr(env, "RATE_LIMIT_PER_SECOND", 3))
            Default.rate_limiter = RateLimiter(
                max_requests_per_second=rate_limit)

    async def fetch(self, request):
        try:
            return await self._handle_request(request)
        except Exception as e:
            # Log exception for debugging (visible in Cloudflare dashboard logs)
            print(f"Unhandled exception: {type(e).__name__}: {e}")
            # Global catch: never leak internal details to client
            return error_response("Internal server error", 500)

    async def _handle_request(self, request):
        method = request.method
        path = urlparse(request.url).path

        # OPTIONS preflight — always allow, no rate limit check
        if method == "OPTIONS":
            return self._preflight_response()

        # Rate limit check
        # CF-Connecting-IP is always set by Cloudflare's edge and cannot be spoofed
        client_ip = request.headers.get("CF-Connecting-IP") or "unknown"

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
