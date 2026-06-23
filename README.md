# ShinobuChat

ShinobuChat is a virtual companion application built around a FastAPI backend, a React/Vite chat interface, Live2D presentation, long-term memory, Todo and synchronization capabilities, voice input/output, and a lightweight skill system.

The active development baseline is the `codex/mvp` branch. The `main` branch is an early prototype and should not be used to rebuild or extend the current application.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer with npm
- PostgreSQL 16 (the default connection is `postgresql+psycopg://postgres:postgres@localhost:5432/shinobuchat`)
- [Docker](https://www.docker.com/) (optional, for containerized PostgreSQL)

Runtime settings are read from environment variables prefixed with `SC_` and from a local `.env` file. `.env` is intentionally ignored by Git and must not contain committed credentials. See `.env.example` for all available options.

## Quick start

### 1. PostgreSQL

**Option A — Docker (recommended for quick setup):**

```powershell
docker compose up -d postgres
```

This starts PostgreSQL 16 with the pgvector extension on port 5432. The database `shinobuchat` is created automatically with user `postgres` / password `postgres`.

**Option B — Local PostgreSQL:**

Install PostgreSQL 16, create a database named `shinobuchat`, and ensure the `pgvector` extension is available:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Environment

```powershell
# Copy the example config (no real secrets in .env.example)
copy .env.example .env
```

Edit `.env` and fill in at minimum:
- `SC_AI_API_KEY` — your LLM API key
- `SC_AI_BASE_URL` / `SC_AI_MODEL` — if not using the OpenAI default
- `SC_JWT_SECRET_KEY` — generate with: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- `SC_CONFIG_ENCRYPTION_KEY` — generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 3. Backend

From the repository root, create and activate a virtual environment, install dependencies, and start FastAPI:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows, `--reload` may not detect file changes out of the box. If auto-reload doesn't trigger, use explicit reload scoping:

```powershell
python -m uvicorn app.main:app --reload --reload-dir D:\ShinobuChat\app --reload-include "*.py"
```

If it still doesn't trigger, restart the backend manually (`Ctrl+C` then re-run).

The API health endpoint is `http://127.0.0.1:8000/health`. Application startup initializes the database schema, so PostgreSQL must be reachable through `SC_DATABASE_URL`.

### 4. Frontend

In a second terminal:

```powershell
cd frontend\shinobu-chat
npm ci
npm run dev
```

The Vite development server runs at `http://localhost:5175` and proxies `/api` requests to `http://127.0.0.1:8000`.

## Docker

A `docker-compose.yml` is provided with:

| Service | Description |
|---|---|
| `postgres` | PostgreSQL 16 + pgvector, port 5432 |
| `backend` | (commented out) optional backend container |

To start only PostgreSQL:

```powershell
docker compose up -d postgres
```

To stop:

```powershell
docker compose down
```

Data persists in a named volume (`pgdata`). To reset: `docker compose down -v`.

## Database

### Schema management

The app auto-creates tables on startup via SQLAlchemy `Base.metadata.create_all()` and applies idempotent column additions for features added after initial table creation. See `docs/db_migration_plan.md` for details.

### SQLite for lightweight testing

For quick experiments without PostgreSQL, set:

```
SC_DATABASE_URL=sqlite:///shinobu_e2e.db
```

SQLite lacks pgvector and some PostgreSQL-specific features (reminders, memory embeddings). Use PostgreSQL for full functionality and final E2E testing.

## Build & deploy

To build the frontend for serving through FastAPI:

```powershell
cd frontend\shinobu-chat
npm run build
```

The build is written to `frontend/shinobu-chat/dist/`. When that directory contains `index.html`, FastAPI serves the built frontend at `/`; otherwise `/` returns a message explaining that the frontend has not been built.

## Tests

Run backend tests from the repository root:

```powershell
python -m pytest tests/ -q
```

Run frontend tests and static checks from `frontend/shinobu-chat`:

```powershell
npm test
npm run typecheck
npm run build
```

## Project structure

- `app/`: FastAPI application, API routes, SQLAlchemy models, schemas, services, event handling, voice pipeline, built-in skills, and Agent orchestration.
- `frontend/shinobu-chat/`: React, TypeScript, and Vite client with chat, Live2D, desktop-pet, media, authentication, and API/SSE integration.
- `characters/`: character definitions, including Shinobu's YAML character card.
- `skills/`: user-facing Markdown skill definitions; built-in Python skill implementations live under `app/skills/`.
- `ios/`: iOS integration and appearance references.
- `tests/`: backend unit and integration-oriented tests.
- `docs/`: architecture, agent documentation, and migration planning.
- `scripts/`: regenerable report and diagram generation utilities.

The backend exposes versioned routes under `/api/v1`, persists application data through SQLAlchemy/PostgreSQL, streams chat and synchronization events over SSE, and can serve a compiled frontend from the Vite `dist` directory.

## Configuration and Skill infrastructure

Authenticated settings endpoints use the current bearer token:

- `GET/PATCH /api/v1/config/user/me` and `PUT /api/v1/config/user/me/reset`
- `GET/POST /api/v1/skills/user/me` plus item-level GET, PUT, PATCH, and DELETE

User overrides are stored in `user_configs` and resolve in this order: database override, environment-backed Settings value, then the Pydantic default. API keys are encrypted with Fernet before persistence and are masked in every public response.

Set a stable production encryption key before saving secrets:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:SC_CONFIG_ENCRYPTION_KEY="<generated-key>"
```

If this variable is absent, development mode derives a key from `SC_JWT_SECRET_KEY`; changing that secret later will make existing encrypted fields unreadable. Production deployments must set both values explicitly.

User Skills are stored as pure `SKILL.md` documents in `user_skills`. YAML frontmatter requires `name` and `description`; only enabled Skill names and descriptions enter the pinned system catalog. Full Markdown is loaded into turn scratch only when the Skill matches or is activated.

## FAQ

### `psql` command not found

PostgreSQL isn't installed or isn't on your PATH. Use Docker instead:

```powershell
docker compose up -d postgres
docker compose exec postgres psql -U postgres -d shinobuchat
```

### PostgreSQL password authentication fails

The default credentials are `postgres` / `postgres`. If you changed the password, update `SC_DATABASE_URL` accordingly:

```
SC_DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/shinobuchat
```

### SQLite vs PostgreSQL

SQLite works for lightweight testing but lacks:
- pgvector (memory embeddings won't work)
- `ADD COLUMN IF NOT EXISTS` (manual column additions target PostgreSQL only)
- Concurrent access safety

For the full feature set and E2E validation, use PostgreSQL.

### Frontend can't connect to backend

Check the Vite proxy in `frontend/shinobu-chat/vite.config.ts` — it forwards `/api` to `http://127.0.0.1:8000`. Ensure the backend is running on port 8000.

### Database tables not created

The backend runs `init_db()` on startup. Check the backend logs for errors. If tables exist but columns are missing, verify you're using PostgreSQL (manual column additions skip non-PostgreSQL dialects).

## E2E verification checklist

- [ ] PostgreSQL is running (`docker compose up -d postgres` or local)
- [ ] `.env` has valid `SC_AI_API_KEY`
- [ ] Backend starts: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- [ ] Health check: `curl http://127.0.0.1:8000/health`
- [ ] Backend tests pass: `python -m pytest tests/ -q`
- [ ] Frontend installs: `cd frontend/shinobu-chat && npm ci`
- [ ] Frontend builds: `npm run build`
- [ ] Frontend dev server: `npm run dev` → `http://localhost:5175`
- [ ] Chat SSE works end-to-end
