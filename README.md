# crypt-api-worker

![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)
![Cloudflare Workers](https://img.shields.io/badge/Cloudflare-Workers-F38020?logo=cloudflare&logoColor=white)

Temporary self-destructing message API built on Cloudflare Workers with Python. Messages are stored in Cloudflare KV and automatically destroyed after being read or after 24 hours — whichever comes first.

## Architecture

**Stack:** Python Worker + Cloudflare KV

The API runs as a [Cloudflare Worker](https://developers.cloudflare.com/workers/) using the Python runtime. Messages are persisted in [Cloudflare KV](https://developers.cloudflare.com/kv/), a global low-latency key-value store, with a 24-hour TTL.

### Data Flow

```
1. POST /             → Generate unique ID → Store message in KV (TTL 24h) → Return { id }
2. GET /{id}          → Fetch message from KV → Return { message } → Delete from KV
3. (after 24h)        → KV automatically expires the key
```

### Project Structure

```
├── src/
│   ├── entry.py          # Worker entrypoint, routing, CORS and rate limiting
│   ├── handlers.py       # Request handlers for POST / and GET /{id}
│   ├── rate_limiter.py   # Sliding-window per-IP rate limiter
│   └── utils.py          # Helpers: ID generation, JSON responses, validation
├── tests/
│   ├── conftest.py       # Shared fixtures
│   ├── test_cors_errors.py
│   ├── test_get.py
│   ├── test_post.py
│   └── test_rate_limiter.py
├── .github/
│   └── workflows/
│       └── deploy.yml    # CI/CD: test + deploy on push to main
├── wrangler.toml         # Cloudflare Workers configuration
├── pyproject.toml        # Project metadata and dev dependencies
└── .env.example          # Environment variable template
```

## Endpoints

### `POST /` — Create a temporary message

| Field | Details |
|-------|---------|
| **Request body** | `{"message": "your secret text"}` |
| **Response** | `{"id": "abc12"}` |
| **Content-Type** | `application/json` |

| Status | Description |
|--------|-------------|
| `200`  | Message created successfully |
| `400`  | Invalid JSON or missing/empty `message` field |
| `413`  | Message exceeds 100 KB |
| `429`  | Rate limit exceeded |
| `500`  | Could not generate a unique ID |

### `GET /{id}` — Retrieve and destroy a message

The message is **deleted immediately** after being read.

| Field | Details |
|-------|---------|
| **Path parameter** | `id` — the 5-character message identifier |
| **Response** | `{"message": "your secret text"}` |

| Status | Description |
|--------|-------------|
| `200`  | Message returned (and destroyed) |
| `404`  | Message not found or already read |
| `429`  | Rate limit exceeded |

## Installation and Setup

### Prerequisites

- [pyenv](https://github.com/pyenv/pyenv) (Python version management)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A [Cloudflare account](https://dash.cloudflare.com/sign-up)

### Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/your-org/crypt-api-worker.git
   cd crypt-api-worker
   ```

2. **Create your environment file**

   ```bash
   cp .env.example .env
   # Fill in CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN
   ```

3. **Install dependencies**

   ```bash
   uv sync
   ```

4. **Create a KV namespace in Cloudflare**

   Go to the [Cloudflare dashboard](https://dash.cloudflare.com/) → Workers & Pages → KV → Create a namespace named `MESSAGES`. Copy the namespace ID and update `wrangler.toml`:

   ```toml
   [[kv_namespaces]]
   binding = "MESSAGES"
   id = "your-namespace-id-here"
   ```

5. **Run locally**

   ```bash
   uv run pywrangler dev
   ```

## Examples

### Create a message

```bash
curl -X POST https://your-worker.workers.dev/ \
  -H "Content-Type: application/json" \
  -d '{"message": "This is a secret message"}'
```

Response:

```json
{"id": "abc12"}
```

### Retrieve a message (self-destructs after reading)

```bash
curl https://your-worker.workers.dev/abc12
```

Response:

```json
{"message": "This is a secret message"}
```

Requesting the same ID again returns:

```json
{"error": "Message not found"}
```

## Tests

Run the full test suite with coverage:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

Minimum required coverage: **80%** (enforced by `pyproject.toml` and CI).

## Deploy

### Manual

```bash
uv run pywrangler deploy
```

Requires `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` environment variables (set in `.env` or exported).

### CI/CD

Automatic deployment on every push to `main` via GitHub Actions (`.github/workflows/deploy.yml`).

**Required GitHub Secrets:**

| Secret | Description |
|--------|-------------|
| `CF_ACCOUNT_ID` | Cloudflare Account ID (found in dashboard) |
| `CF_API_TOKEN` | Cloudflare API Token with Workers permissions |

## Limitations

- **Free tier quotas:** 100,000 reads/day, 1,000 writes/day, 1,000 deletes/day per KV namespace.
- **Rate limiter is per-isolate:** Each Cloudflare Worker isolate maintains its own in-memory rate limiter. This is not globally consistent across edge locations.
- **Messages are not encrypted:** Messages are stored as plain text in KV. Do not use this for highly sensitive data without adding client-side encryption.
- **TTL is fixed at 24 hours:** The expiration time is not configurable per message.
