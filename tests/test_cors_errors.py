"""Tests for CORS headers and error responses."""

import pytest

from tests.conftest import MockRequest


async def test_cors_headers_on_success(worker, kv):
    """Successful responses include CORS headers."""
    await kv.put("cors1", "hi")
    request = MockRequest(
        method="GET",
        url="https://example.com/cors1",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"


async def test_cors_headers_on_error(worker):
    """Error responses also include CORS headers."""
    request = MockRequest(
        method="GET",
        url="https://example.com/missing",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 404
    assert response.headers["Access-Control-Allow-Origin"] == "*"


async def test_preflight_options_returns_204(worker):
    """OPTIONS request → 204 with CORS headers, no body."""
    request = MockRequest(
        method="OPTIONS",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 204
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert response.body is None


async def test_deep_path_returns_404(worker):
    """GET /nonexistent/deep/path → 404."""
    request = MockRequest(
        method="GET",
        url="https://example.com/nonexistent/deep/path",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 404
    assert "Not found" in response.json_body()["error"]


async def test_put_root_returns_405(worker):
    """PUT / → 405."""
    request = MockRequest(
        method="PUT",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 405
    assert "not allowed" in response.json_body()["error"].lower()


async def test_delete_root_returns_405(worker):
    """DELETE / → 405."""
    request = MockRequest(
        method="DELETE",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 405


async def test_unhandled_exception_returns_500(worker):
    """Internal exception → generic 500 error."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "boom"},
    )

    # Force an exception inside _handle_request by breaking env
    worker.env = None
    response = await worker.fetch(request)

    assert response.status == 500
    assert "Failed to save message" in response.json_body()["error"]


async def test_rate_limited_returns_429(worker):
    """Exceeding rate limit → 429."""
    for i in range(3):
        req = MockRequest(
            method="GET",
            url=f"https://example.com/id{i}",
            headers={"CF-Connecting-IP": "10.0.0.1"},
        )
        await worker.fetch(req)

    request = MockRequest(
        method="GET",
        url="https://example.com/anymsg",
        headers={"CF-Connecting-IP": "10.0.0.1"},
    )
    response = await worker.fetch(request)

    assert response.status == 429
    assert "Rate limit" in response.json_body()["error"]
    assert response.headers["Access-Control-Allow-Origin"] == "*"


async def test_post_on_single_segment_returns_405(worker):
    """POST /{id} → 405 (only GET allowed for ID route)."""
    request = MockRequest(
        method="POST",
        url="https://example.com/someid",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 405
