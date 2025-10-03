# Telegabot Service (Python)

FastAPI-based service that queues and executes Telegram automation jobs using Telethon and MySQL persistence. The service stores every piece of state in MySQL, including job queue data, execution logs, account sessions, and ruleset definitions.

## Features

- Account management with AES-256-GCM encryption of sensitive credentials and Telethon StringSession storage.
- REST API for enqueuing single Telegram actions or multi-step rulesets.
- Synchronous job executor (`POST /api/v1/jobs/{id}/execute`) that serializes access per Telegram account using MySQL `GET_LOCK` and performs optimistic session updates.
- Detailed action and error logging stored in MySQL, including per-step retry counters.
- Schema-first approach with `schema.sql` and JSONSchema references for action contracts.
- Configurable execution timeouts and heartbeat tracking for external worker orchestration.

## Project Layout

```
app/
  api/            # FastAPI routers
  core/           # configuration, security, auth helpers
  db/             # SQLAlchemy setup
  models/         # ORM models
  schemas/        # Pydantic request/response models
  services/       # Business logic for accounts, jobs, logging
  utils/          # Context templating utilities
  workers/        # Job execution and Telegram action runners
schema.sql        # Database schema and seed data
pyproject.toml    # Python project metadata and dependencies
```

## Requirements

- Python 3.11+
- MySQL 8+
- Access to a Telegram application API ID/hash for each Telegram account

## Setup

1. **Install dependencies**

   ```bash
   pip install -e .
   ```

2. **Create and seed the database**

   ```bash
   mysql -u <user> -p < schema.sql
   ```

3. **Configure environment**

   Copy `.env.example` to `.env` and edit values:

   ```bash
   cp .env.example .env
   ```

   Required variables:

   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`
   - `API_KEY` – API key for `x-api-key` header
   - `APP_KMS_KEY` – 32-byte key (raw or hex) for AES-256-GCM field encryption
   - Execution tuning: `JOB_EXEC_TIMEOUT_S`, `ACCOUNT_LOCK_TIMEOUT_S`, `HEARTBEAT_INTERVAL_S`, `JOB_STALE_TIMEOUT_S`

4. **Run the service**

   ```bash
   uvicorn app.main:app --reload
   ```

   The `/health` endpoint verifies database connectivity and exposes the build version.

## REST API Overview

All endpoints except `/` and `/health` require the `x-api-key` header.

### Accounts

- `POST /api/v1/accounts` – create Telegram account entries.
- `GET /api/v1/accounts` – list accounts with recent activity summaries.
- `GET /api/v1/accounts/{id}` – account details, last 10 action logs, and last 3 error logs.

### Queue

- `POST /api/v1/queue/login`
- `POST /api/v1/queue/logout`
- `POST /api/v1/queue/channels/open`
- `POST /api/v1/queue/posts/read`
- `POST /api/v1/queue/rulesets/{id}/run`

Each endpoint enqueues a job with status `pending` and returns `{ "jobId": number }`.

### Jobs

- `GET /api/v1/jobs/{id}` – job status and context.
- `GET /api/v1/jobs/{id}/steps` – step-by-step execution data with retry counts.
- `POST /api/v1/jobs/{id}/execute` – synchronous execution for MVP worker semantics.

### Logs

- `GET /api/v1/logs/actions` – filterable business event log.
- `GET /api/v1/logs/errors` – filterable error log.

### Rulesets

- `POST /api/v1/rulesets` – create reusable rule definitions with templated inputs and result expressions.

### Health

- `GET /health` – database connectivity probe with build metadata.

## Docker

A sample `docker-compose.yml` is provided for local development with MySQL 8 and the FastAPI service (see below).

```bash
docker compose up --build
```

## Testing Checklist

- Enqueue LOGIN creates a pending job and step.
- Executing LOGIN updates `session_blob` and increments `session_version` when the Telethon session changes.
- OPEN_CHANNEL execution returns posts and logs the step outcome.
- READ_POST with an invalid message id records an `error_logs` entry and marks the job as failed.
- Parallel execution for different accounts succeeds; same-account execution enforces `ACCOUNT_BUSY` via `GET_LOCK` timeout.
