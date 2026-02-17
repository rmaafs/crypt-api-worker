from src.utils import error_response, generate_id, json_response, validate_message_size

MAX_ID_ATTEMPTS = 10
KV_TTL_SECONDS = 86400  # 24 hours


async def handle_create_message(request, env):
    """POST / — Create a new self-destructing message."""
    # Parse JSON body
    try:
        body = await request.json()
    except Exception:
        return error_response("Invalid JSON body", 400)

    # Validate message field exists and is not empty
    message = body.get("message") if isinstance(body, dict) else None
    if not message or not isinstance(message, str) or not message.strip():
        return error_response("Field 'message' is required and cannot be empty", 400)

    # Validate body size <= 100KB
    if not validate_message_size(message):
        return error_response("Message exceeds maximum size of 100KB", 413)

    # Generate unique ID with collision check (max 10 attempts)
    for _ in range(MAX_ID_ATTEMPTS):
        msg_id = generate_id()
        existing = await env.MESSAGES.get(msg_id)
        if existing is None:
            break
    else:
        return error_response("Could not generate a unique ID. Please try again.", 500)

    # Save message in KV with 24h TTL
    await env.MESSAGES.put(msg_id, message, expiration_ttl=KV_TTL_SECONDS)

    return json_response({"id": msg_id})


async def handle_get_message(message_id, env):
    """GET /{id} — Retrieve and delete a self-destructing message."""
    message = await env.MESSAGES.get(message_id)

    if message is None:
        return error_response("Message not found", 404)

    # Always delete the message after reading, guaranteed by try/finally
    try:
        return json_response({"message": message})
    finally:
        await env.MESSAGES.delete(message_id)
