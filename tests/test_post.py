"""Tests for POST / endpoint (create message)."""

import re
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import MockEnv, MockKV, MockRequest


async def test_create_message_happy_path(worker, kv):
    """POST / with valid message returns 200 and a 5-char ID."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "hello"},
    )
    response = await worker.fetch(request)
    body = response.json_body()

    assert response.status == 200
    assert "id" in body
    assert re.fullmatch(r"[a-z0-9]{5}", body["id"])


async def test_message_saved_in_kv_with_ttl(worker, kv):
    """Created message is persisted in KV."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "stored-value"},
    )
    response = await worker.fetch(request)
    msg_id = response.json_body()["id"]

    stored = await kv.get(msg_id)
    assert stored == "stored-value"


async def test_empty_body_returns_400(worker):
    """POST / with no body → 400."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body=None,
    )
    response = await worker.fetch(request)

    assert response.status == 400
    assert "Invalid JSON body" in response.json_body()["error"]


async def test_body_without_message_field_returns_400(worker):
    """POST / with JSON missing 'message' → 400."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"data": "something"},
    )
    response = await worker.fetch(request)

    assert response.status == 400
    assert "message" in response.json_body()["error"].lower()


async def test_empty_message_returns_400(worker):
    """POST / with empty string message → 400."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "   "},
    )
    response = await worker.fetch(request)

    assert response.status == 400
    assert "message" in response.json_body()["error"].lower()


async def test_message_over_100kb_returns_413(worker):
    """POST / with message > 100KB → 413."""
    big_message = "x" * (102400 + 1)
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": big_message},
    )
    response = await worker.fetch(request)

    assert response.status == 413
    assert "100KB" in response.json_body()["error"]


async def test_invalid_json_body_returns_400(worker):
    """POST / with un-parseable body → 400."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body="not-json{{{",
    )
    response = await worker.fetch(request)

    assert response.status == 400
    assert "Invalid JSON" in response.json_body()["error"]


async def test_id_collision_regenerates(worker, kv, env):
    """When KV already has a key, a new ID is generated."""
    # Pre-populate many keys but leave room for success
    call_count = 0
    original_get = kv.get

    async def mock_get(key):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return "existing"
        return None

    kv.get = mock_get

    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "collision-test"},
    )
    response = await worker.fetch(request)

    assert response.status == 200
    assert call_count >= 3


async def test_persistent_collision_returns_500(worker, kv):
    """When all 10 ID attempts collide → 500."""

    async def always_exists(key):
        return "exists"

    kv.get = always_exists

    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": "will-fail"},
    )
    response = await worker.fetch(request)

    assert response.status == 500
    assert "unique ID" in response.json_body()["error"]


async def test_message_exactly_100kb_accepted(worker, kv):
    """Message with exactly 100KB should be accepted (inclusive limit)."""
    exact_message = "x" * 102400
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body={"message": exact_message},
    )
    response = await worker.fetch(request)

    assert response.status == 200
    assert "id" in response.json_body()


async def test_body_is_list_returns_400(worker):
    """POST / with a JSON array body → 400 (body.get would fail)."""
    request = MockRequest(
        method="POST",
        url="https://example.com/",
        headers={"CF-Connecting-IP": "1.2.3.4"},
        body=["not", "a", "dict"],
    )
    response = await worker.fetch(request)

    assert response.status == 400
