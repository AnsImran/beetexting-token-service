# BEEtexting Token Service

Internal microservice that manages BEEtexting OAuth2 tokens. It fetches tokens via the **client-credentials** flow, caches them in memory as validated **Pydantic v2 models**, and **proactively refreshes** them before expiry using a background asyncio loop.

Sibling microservices (e.g. the SMS sender, worklist service) call `GET /api/v1/token` to obtain a ready-to-use Bearer token instead of managing credentials themselves.

---

## Architecture

![Architecture Diagram](docs/architecture.png)

**How it works:**

1. Sibling services call the Token Service (`GET /api/v1/token`) to get a cached Bearer token.
2. The Token Service's background loop refreshes the token from BEEtexting's OAuth2 endpoint before it expires.
3. Sibling services use the token directly against BEEtexting's SMS API (`connect.beetexting.com`).

The Token Service binds to **localhost only** (`127.0.0.1:8100`) — it is never exposed to the internet. Only internal services on the same server can reach it.

---

## Token Lifecycle

![Token Lifecycle Diagram](docs/token_lifecycle.png)

| Phase | What happens |
|-------|-------------|
| **Startup** | `TokenManager.start()` is called during FastAPI lifespan |
| **Initial fetch** | `POST` to `auth.beetexting.com/oauth2/token/` with client credentials |
| **Validate & cache** | Raw JSON is validated through `BeeTextingTokenResponse`, then stored as a frozen `CachedToken` |
| **Serve callers** | `GET /api/v1/token` returns the cached token instantly (no HTTP call) |
| **Background refresh** | Sleeps until `buffer` seconds before expiry, then repeats from "Initial fetch" |

The token is refreshed **5 minutes before expiry** by default (configurable via `TOKEN_REFRESH_BUFFER_SECONDS`). With a 1-hour token lifetime, this means ~1 refresh request per hour.

---

## Quick Start

```bash
# 1. Install dependencies (requires uv — https://docs.astral.sh/uv/)
uv sync --all-extras

# 2. Configure credentials
cp .env.example .env
# Edit .env with your real BEEtexting credentials

# 3. Run the service
uv run python main.py
# → Listening on http://127.0.0.1:8100

# 4. Verify it's working
curl http://127.0.0.1:8100/api/v1/health
curl http://127.0.0.1:8100/api/v1/token
```

---

## API Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/v1/token` | Returns the current Bearer token + API key + expiry | `TokenResponse` |
| `GET` | `/api/v1/health` | Health check — reports `healthy` or `degraded` | `HealthResponse` |
| `GET` | `/api/v1/ping` | Bare-minimum liveness probe (no dependencies) | `{"ping": "pong"}` |
| `GET` | `/docs` | Interactive OpenAPI (Swagger UI) documentation | HTML |
| `GET` | `/redoc` | ReDoc API documentation | HTML |

### Example: `GET /api/v1/token`

```json
{
  "ok": true,
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_at_utc": "2026-04-11T13:00:00+00:00",
  "api_key": "your-api-key-here"
}
```

### Example: `GET /api/v1/health`

```json
{
  "status": "healthy",
  "has_valid_token": true,
  "token_expires_at_utc": "2026-04-11T13:00:00+00:00"
}
```

### Error responses

All errors return a consistent JSON envelope:

```json
{
  "ok": false,
  "error": {
    "code": 503,
    "message": "No valid token is currently available."
  }
}
```

| HTTP Code | When |
|-----------|------|
| `502` | Failed to fetch token from BEEtexting (upstream error) |
| `503` | No valid token in memory (service just started or all retries failed) |
| `500` | Unexpected internal error |

---

## Configuration

All settings are loaded from environment variables (or a `.env` file in the project root). See [.env.example](.env.example) for the full list with descriptions and defaults.

### Required

| Variable | Description |
|----------|-------------|
| `BEETEXTING_CLIENT_ID` | OAuth2 client ID for the BEEtexting M2M application |
| `BEETEXTING_CLIENT_SECRET` | OAuth2 client secret for the BEEtexting M2M application |
| `BEETEXTING_API_KEY` | API key sent as `x-api-key` header on every BEEtexting request |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `BEETEXTING_TOKEN_URL` | `https://auth.beetexting.com/oauth2/token/` | OAuth2 token endpoint |
| `BEETEXTING_SCOPES` | `ReadContact WriteContact SendMessage` | Space-separated OAuth2 scopes |
| `TOKEN_REFRESH_BUFFER_SECONDS` | `300` | Refresh this many seconds before token expiry (min: 30) |
| `TOKEN_RETRY_ATTEMPTS` | `3` | Number of retries on failed token fetch (1–10) |
| `TOKEN_RETRY_DELAY_SECONDS` | `2.0` | Base delay between retries, doubles each time (0.5–30) |
| `HTTP_TIMEOUT_SECONDS` | `10.0` | Timeout for HTTP calls to BEEtexting (1–60) |
| `APP_HOST` | `127.0.0.1` | Host to bind to (localhost = internal only) |
| `APP_PORT` | `8100` | Port to bind to (1024–65535) |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `ACCESS_LOG_LEVEL` | `INFO` | Uvicorn HTTP access log level — `INFO` shows every request, `WARNING` silences them |

All values are validated at startup via **Pydantic Settings**. If a required variable is missing or a value is out of range, the service fails fast with a clear error message.

---

## Usage from Another Service

Sibling microservices call the token endpoint to get a ready-to-use token:

```python
import httpx

# Fetch token from the Token Service
response = httpx.get("http://127.0.0.1:8100/api/v1/token")
data = response.json()

# Use these in your BEEtexting API calls:
token   = data["access_token"]      # → Authorization: Bearer <token>
api_key = data["api_key"]           # → x-api-key: <api_key>
expires = data["expires_at_utc"]    # → know when it goes stale

# Example: send an SMS via BEEtexting
sms_response = httpx.post(
    "https://connect.beetexting.com/prod/message/sendsms",
    headers={
        "Authorization": f"Bearer {token}",
        "x-api-key": api_key,
    },
    params={
        "from": "+1XXXXXXXXXX",
        "to": "+1XXXXXXXXXX",
        "text": "Hello from the microservice!",
    },
)
```

---

## Pydantic v2 Data Models

All data flowing through the service is validated by Pydantic v2 models. Internal value objects (`BeeTextingTokenResponse`, `CachedToken`) are **frozen** (immutable), and `access_token` fields use `repr=False` so tokens never leak into logs.

Schemas live in [src/schemas/](src/schemas/) split by domain:

| File | Models |
|------|--------|
| [`token.py`](src/schemas/token.py) | `BeeTextingTokenResponse`, `CachedToken`, `TokenResponse` |
| [`health.py`](src/schemas/health.py) | `HealthResponse` |
| [`errors.py`](src/schemas/errors.py) | `ErrorDetail`, `ErrorResponse` |

### `BeeTextingTokenResponse` — upstream API validation (internal)

Validates the raw JSON from BEEtexting's OAuth2 endpoint before we trust it.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `access_token` | `str` | `min_length=1`, `repr=False` | The Bearer token |
| `token_type` | `str` | default `"Bearer"` | Always "Bearer" |
| `expires_in` | `int` | `gt=0` | Seconds until expiry |

Uses `populate_by_name=True` with explicit field aliases matching BEEtexting's JSON keys, so if their API ever renames a field we update the alias, not our code.

### `CachedToken` — in-memory state (internal)

The single token object held by `TokenManager`. Created on every refresh, atomically swapped under an asyncio lock.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `access_token` | `str` | `min_length=1`, `repr=False` | The Bearer token |
| `token_type` | `str` | default `"Bearer"` | Always "Bearer" |
| `expires_at_utc` | `datetime` | UTC-aware | When this token expires |
| `fetched_at_utc` | `datetime` | UTC-aware | When this token was fetched |
| `.is_expired` | `bool` (property) | — | `True` if current time ≥ expiry |

### `TokenResponse` — outbound, `GET /api/v1/token`

The JSON body returned to sibling services.

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` (default `true`) | Request succeeded flag |
| `access_token` | `str` | Bearer token to pass to BEEtexting |
| `token_type` | `str` (default `"Bearer"`) | Token type |
| `expires_at_utc` | `datetime` | When the token goes stale |
| `api_key` | `str` | The `x-api-key` header value required alongside the Bearer token |

### `HealthResponse` — outbound, `GET /api/v1/health`

| Field | Type | Description |
|-------|------|-------------|
| `status` | `str` | `"healthy"` or `"degraded"` |
| `has_valid_token` | `bool` | Whether a usable token is in memory |
| `token_expires_at_utc` | `datetime \| None` | UTC expiry, or null if no token |

### `ErrorResponse` / `ErrorDetail` — standard error envelope

Every failure response (502, 503, 500) uses this shape:

```json
{
  "ok": false,
  "error": { "code": 503, "message": "No valid token is currently available." }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` (default `false`) | Success flag |
| `error.code` | `int` | HTTP status code |
| `error.message` | `str` | Human-readable description |

---

## BEEtexting API Rate Limits & Constraints

BEEtexting does **not publicly document** API-level rate limits. The information below was compiled from their documentation portal, pricing pages, FAQ, and carrier-level 10DLC regulations.

### OAuth2 Token Endpoint

| Item | Value |
|------|-------|
| **Token lifetime** | 3600 seconds (1 hour) |
| **Grant type** | `client_credentials` (M2M, no user interaction) |
| **Token request rate limit** | Not documented — returns HTTP `429` if exceeded |
| **Our request rate** | ~1 request/hour (well within any reasonable limit) |
| **Token caching** | Yes — we cache and reuse, refresh 5 min before expiry |

### Account/Plan Message Limits

| Item | Value |
|------|-------|
| **Messages included per month** | 1,000 (all plans) |
| **Overage cost (per message)** | $0.04 |
| **SMS cost (per segment)** | $0.0199 |
| **MMS cost (per segment)** | $0.0399 |
| **SMS segment size** | 160 characters |
| **Messages > 160 chars** | Billed as multiple segments |
| **API access** | Enterprise plan only ($1,969.50/mo) |
| **Message history retention** | Professional: 1yr, Premium: 2yr, Enterprise: unlimited |

### Carrier-Level 10DLC Throughput (the real bottleneck)

BEEtexting uses 10-digit long code (10DLC) numbers. **Carriers enforce per-second throughput limits** based on your brand's Trust Score from The Campaign Registry (TCR), regardless of what BEEtexting's API allows.

#### Standard Brand Campaigns

| Trust Score | AT&T (MPS) | T-Mobile (MPS) | Verizon (MPS) | **Total MPS** |
|-------------|-----------|----------------|--------------|---------------|
| 75–100 | 75 | 75 | 75 | **225** |
| 50–74 | 40 | 40 | 40 | **120** |
| 1–49 | 4 | 4 | 4 | **12** |
| 0 (Low Vol) | 4 | 4 | 4 | **12** |

> MPS = Messages Per Second

#### Sole Proprietor (worst case)

| Carrier | Limit |
|---------|-------|
| AT&T | 0.25 MPS (15 msg/min) |
| T-Mobile | 1 MPS per number (1,000 msg/day cap) |
| Verizon | 1 MPS per number |
| **Total** | **2.25 MPS** |

#### What this means for us

- **Token requests are not a concern.** We make ~1 request/hour. Any rate limit is orders of magnitude above that.
- **Message throughput is carrier-gated**, not API-gated. The real limit is 4–75 MPS per carrier depending on Trust Score.
- **Monthly volume is plan-gated.** 1,000 included messages, then $0.04/msg overage.
- **Our `TOKEN_REFRESH_BUFFER_SECONDS=300` is correct.** One fresh token per hour is optimal.

---

## Error Handling

The service uses a centralised exception hierarchy:

```
Exception
  └── TokenServiceError (base, 500)
        ├── TokenFetchError (502) — upstream BEEtexting call failed
        └── TokenNotAvailableError (503) — no valid token in memory
```

All exceptions are caught by FastAPI error handlers registered at startup. Every error response uses the same JSON envelope (`{"ok": false, "error": {"code": N, "message": "..."}}`), so consuming services can parse errors reliably.

Unhandled exceptions are caught by a generic handler that logs the full traceback but returns a generic message — internal details never leak to callers.

---

## Logging

- **Format:** `2026-04-11T12:34:56.789+00:00 | INFO | module:func:42 | message`
- **Timezone:** All timestamps are UTC with `+00:00` suffix
- **Output:** stdout (for Docker / systemd capture)
- **App level:** Configurable via `LOG_LEVEL` env var (default `INFO`)
- **HTTP access log:** Controlled separately via `ACCESS_LOG_LEVEL` (default `INFO` = every request is logged; set to `WARNING` in production to silence)
- **Suppressed:** `httpx` and `httpcore` are pinned to `WARNING` to cut noise from the token-refresh HTTP calls

---

## Testing

```bash
# Run all tests with verbose output
uv run pytest -v

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run only a specific test class
uv run pytest tests/test_token_manager.py::TestCachedTokenSchema -v

# Lint check
uv run ruff check src/ tests/
```

### Test coverage

- **37 tests** across 3 test files (plus shared fixtures in `conftest.py`)
- **85%+ code coverage**
- All HTTP calls are mocked with `respx` — tests never touch real BEEtexting

| Test file | What it covers |
|-----------|---------------|
| `test_config.py` | Settings validation, defaults, field constraints |
| `test_token_manager.py` | Token fetch, retry logic, expiry, background refresh timing, Pydantic model validation (frozen, repr, min_length, aliases, is_expired) |
| `test_api.py` | API endpoint responses (token, health, ping), error responses |

---

## Project Structure

![Project Structure Diagram](docs/project_structure.png)

> The diagram above is rendered from the Mermaid source below. GitHub renders it natively; for offline viewing re-run `python docs/render_project_structure.py`.

```mermaid
flowchart TB
    main["<b>main.py</b><br/>Entrypoint<br/>(uvicorn startup)"]

    subgraph SRC["src/"]
        direction TB
        app["<b>app.py</b><br/>FastAPI factory<br/>Lifespan mgmt"]

        subgraph CORE["core/ — cross-cutting"]
            direction LR
            config["config.py<br/>Pydantic Settings"]
            exceptions["exceptions.py<br/>Errors + handlers"]
            logging["logging_config.py<br/>UTC logging"]
        end

        subgraph SCHEMAS["schemas/ — Pydantic v2 models"]
            direction LR
            s_token["token.py<br/>BeeTextingTokenResponse<br/>CachedToken<br/>TokenResponse"]
            s_health["health.py<br/>HealthResponse"]
            s_errors["errors.py<br/>ErrorResponse"]
        end

        subgraph SERVICES["services/ — business logic"]
            tm["token_manager.py<br/>TokenManager<br/>(fetch / cache / refresh)"]
        end

        subgraph API["api/v1/ — HTTP layer"]
            router["router.py<br/>/token  /health  /ping"]
        end
    end

    main --> app
    app --> config
    app --> exceptions
    app --> logging
    app --> tm
    app --> router

    tm --> config
    tm --> exceptions
    tm --> s_token

    router --> config
    router --> tm
    router --> s_token
    router --> s_health
    router --> s_errors

    classDef entry fill:#7C3AED,stroke:#1E3A5F,color:#fff,font-weight:bold
    classDef core fill:#059669,stroke:#1E3A5F,color:#fff
    classDef schemas fill:#EC4899,stroke:#1E3A5F,color:#fff
    classDef services fill:#F59E0B,stroke:#1E3A5F,color:#1E3A5F,font-weight:bold
    classDef api fill:#6366F1,stroke:#1E3A5F,color:#fff
    classDef app fill:#3B7DD8,stroke:#1E3A5F,color:#fff,font-weight:bold

    class main entry
    class app app
    class config,exceptions,logging core
    class s_token,s_health,s_errors schemas
    class tm services
    class router api
```

```
beetexting_token_service/
├── main.py                                  # Entrypoint (uvicorn startup)
├── pyproject.toml                           # Dependencies, ruff, pytest config
├── .env.example                             # Environment variable template
├── .env                                     # Real secrets (gitignored)
├── .gitignore
├── README.md                                # This file
│
├── src/
│   ├── __init__.py
│   ├── app.py                               # FastAPI factory + lifespan
│   │
│   ├── core/                                # Cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── config.py                        # Pydantic Settings (all env vars, validated)
│   │   ├── exceptions.py                    # Custom errors + FastAPI error handlers
│   │   └── logging_config.py                # Structured UTC logging setup
│   │
│   ├── schemas/                             # Pydantic v2 models split by domain
│   │   ├── __init__.py
│   │   ├── token.py                         # BeeTextingTokenResponse, CachedToken, TokenResponse
│   │   ├── health.py                        # HealthResponse
│   │   └── errors.py                        # ErrorDetail, ErrorResponse
│   │
│   ├── services/                            # Business logic
│   │   ├── __init__.py
│   │   └── token_manager.py                 # TokenManager — fetch / cache / background refresh
│   │
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           └── router.py                    # Versioned endpoints: /token /health /ping
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                          # Shared fixtures (fake settings, test client)
│   ├── test_config.py                       # Config validation tests
│   ├── test_token_manager.py                # Core logic + Pydantic model tests
│   └── test_api.py                          # API endpoint tests
│
└── docs/
    ├── generate_diagrams.py                 # matplotlib → architecture + token_lifecycle (PNG + SVG)
    ├── render_project_structure.py          # Mermaid → project_structure.png via mermaid.ink
    ├── architecture.png / .svg              # High-level architecture
    ├── token_lifecycle.png / .svg           # Token fetch / cache / refresh lifecycle
    └── project_structure.png                # Module dependency map (rendered from README Mermaid block)
```

---

## Regenerating Diagrams

The project uses **two different approaches** for diagrams:

### 1. `architecture` and `token_lifecycle` — matplotlib

These are hand-positioned diagrams generated with matplotlib. They output both PNG and SVG so they can be fine-tuned in Inkscape or Figma:

```bash
# Requires matplotlib (pip install matplotlib)
python docs/generate_diagrams.py
```

### 2. `project_structure` — Mermaid

This one uses a Mermaid flowchart embedded directly in the README (see the [Project Structure](#project-structure) section). Mermaid handles layout automatically, so arrows never overlap and the diagram is trivial to update — just edit the ```` ```mermaid ```` block in the README and re-render:

```bash
# Stdlib only, no dependencies needed
python docs/render_project_structure.py
```

This sends the Mermaid source to [mermaid.ink](https://mermaid.ink) and saves the PNG to `docs/project_structure.png`. GitHub also renders the Mermaid block natively when viewing the README online, so the PNG is only needed for offline viewing.

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Runtime | Python | 3.12+ |
| Web framework | FastAPI | 0.115+ |
| HTTP server | Uvicorn | 0.34+ |
| HTTP client | httpx | 0.28+ (async) |
| Validation | Pydantic v2 | 2.10+ |
| Configuration | pydantic-settings | 2.7+ |
| Package manager | uv | latest |
| Testing | pytest + pytest-asyncio | 8+ |
| HTTP mocking | respx | 0.22+ |
| Linting | ruff | 0.9+ |
