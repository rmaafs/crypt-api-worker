import json
import random
import string

from workers import Response

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def generate_id(length=5):
    """Generate a random ID of `length` chars using a-z0-9."""
    charset = string.ascii_lowercase + string.digits
    return "".join(random.choices(charset, k=length))


def validate_message_size(body, max_bytes=102400):
    """Return True if body size is within limit, False if it exceeds 100KB."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return len(body) <= max_bytes


def json_response(data, status=200, cors=True):
    """Create a Response with JSON body and appropriate headers."""
    headers = {"Content-Type": "application/json"}
    if cors:
        headers.update(CORS_HEADERS)
    return Response(json.dumps(data), status=status, headers=headers)


def error_response(message, status, cors=True):
    """Create an error Response with {"error": message} format."""
    return json_response({"error": message}, status=status, cors=cors)
