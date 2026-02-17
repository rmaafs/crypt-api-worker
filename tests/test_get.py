"""Tests for GET /{id} endpoint (retrieve and delete message)."""

import pytest

from tests.conftest import MockRequest


async def test_get_message_happy_path(worker, kv):
    """GET /{id} with existing message → 200 with message content."""
    await kv.put("abc12", "hello")
    request = MockRequest(
        method="GET",
        url="https://example.com/abc12",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)
    body = response.json_body()

    assert response.status == 200
    assert body["message"] == "hello"


async def test_message_deleted_after_reading(worker, kv):
    """Message is removed from KV after a successful GET."""
    await kv.put("del01", "secret")
    request = MockRequest(
        method="GET",
        url="https://example.com/del01",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    await worker.fetch(request)

    remaining = await kv.get("del01")
    assert remaining is None


async def test_nonexistent_id_returns_404(worker, kv):
    """GET /{id} for missing key → 404."""
    request = MockRequest(
        method="GET",
        url="https://example.com/nope0",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)

    assert response.status == 404
    assert "not found" in response.json_body()["error"].lower()


async def test_unicode_emoji_message(worker, kv):
    """GET /{id} with unicode/emoji content."""
    await kv.put("emoji", "Hello 🌍🔑!")
    request = MockRequest(
        method="GET",
        url="https://example.com/emoji",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    response = await worker.fetch(request)
    body = response.json_body()

    assert response.status == 200
    assert body["message"] == "Hello 🌍🔑!"


async def test_delete_called_even_on_success(worker, kv):
    """The finally block ensures delete is always invoked."""
    deleted_keys = []
    original_delete = kv.delete

    async def tracking_delete(key):
        deleted_keys.append(key)
        await original_delete(key)

    kv.delete = tracking_delete

    await kv.put("track", "value")
    request = MockRequest(
        method="GET",
        url="https://example.com/track",
        headers={"CF-Connecting-IP": "1.2.3.4"},
    )
    await worker.fetch(request)

    assert "track" in deleted_keys
