"""Shared fixtures and mocks for testing the crypt-api-worker.

The `workers` module is only available in the Cloudflare runtime, so we inject
a mock version into sys.modules BEFORE any source code is imported.
"""

import json
import sys
import types

# ---------------------------------------------------------------------------
# Mock `workers` module — must be set up before any src imports
# ---------------------------------------------------------------------------

_mock_workers = types.ModuleType("workers")


class MockResponse:
    """Minimal stand-in for workers.Response."""

    def __init__(self, body=None, *, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = dict(headers) if headers else {}

    def json_body(self):
        """Helper to parse the body as JSON."""
        if self.body is None:
            return None
        return json.loads(self.body)


class MockWorkerEntrypoint:
    """Minimal stand-in for workers.WorkerEntrypoint."""

    def __init__(self, env=None, ctx=None):
        self.env = env
        self.ctx = ctx


_mock_workers.Response = MockResponse
_mock_workers.WorkerEntrypoint = MockWorkerEntrypoint

sys.modules["workers"] = _mock_workers

# ---------------------------------------------------------------------------
# Now it's safe to import source modules
# ---------------------------------------------------------------------------

import pytest  # noqa: E402

from src.entry import Default  # noqa: E402
from src.rate_limiter import RateLimiter  # noqa: E402


# ---------------------------------------------------------------------------
# Mock KV namespace
# ---------------------------------------------------------------------------

class MockKV:
    """In-memory KV store that mimics the Cloudflare KV namespace API."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def put(self, key: str, value: str, *, expiration_ttl: int | None = None):
        self._store[key] = value

    async def delete(self, key: str):
        self._store.pop(key, None)


# ---------------------------------------------------------------------------
# Mock env
# ---------------------------------------------------------------------------

class MockEnv:
    """Simulates the Cloudflare Worker env bindings."""

    def __init__(self, kv: MockKV | None = None, rate_limit: int = 3):
        self.MESSAGES = kv or MockKV()
        self.RATE_LIMIT_PER_SECOND = rate_limit


# ---------------------------------------------------------------------------
# Mock request
# ---------------------------------------------------------------------------

class MockRequest:
    """Simulates an incoming HTTP request."""

    def __init__(
        self,
        method: str = "GET",
        url: str = "https://example.com/",
        headers: dict | None = None,
        body: object = None,
    ):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self._body = body

    async def json(self):
        if self._body is None:
            raise ValueError("No body")
        if isinstance(self._body, str):
            return json.loads(self._body)
        return self._body


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def kv():
    """Fresh MockKV for each test."""
    return MockKV()


@pytest.fixture()
def env(kv):
    """Fresh MockEnv bound to a fresh KV."""
    return MockEnv(kv=kv)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the class-level rate limiter between tests."""
    Default.rate_limiter = None
    yield


@pytest.fixture()
def worker(env):
    """Return a Default worker instance wired to the given env."""
    # Call __init__ properly with env and ctx (ctx can be None for tests)
    instance = Default(env, ctx=None)
    return instance
