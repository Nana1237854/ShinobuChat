# ShinobuChat

ShinobuChat is a virtual companion application built around a FastAPI backend, a React/Vite chat interface, Live2D presentation, long-term memory, Todo and synchronization capabilities, voice input/output, and a lightweight skill system.

The active development baseline is the `codex/mvp` branch. The `main` branch is an early prototype and should not be used to rebuild or extend the current application.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer with npm
- PostgreSQL (the default connection is `postgresql+psycopg://postgres:postgres@localhost:5432/shinobuchat`)

Runtime settings are read from environment variables prefixed with `SC_` and from a local `.env` file. `.env` is intentionally ignored by Git and must not contain committed credentials. Important settings include `SC_DATABASE_URL`, LLM API keys and base URLs, and optional ASR/TTS service settings.

## Backend

From the repository root, create and activate a virtual environment, install dependencies, and start FastAPI:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API health endpoint is `http://127.0.0.1:8000/health`. Application startup initializes the database schema, so PostgreSQL must be reachable through `SC_DATABASE_URL`.

## Frontend

In a second terminal:

```powershell
cd frontend\shinobu-chat
npm ci
npm run dev
```

The Vite development server runs at `http://localhost:5175` and proxies `/api` requests to `http://127.0.0.1:8000`.

To build the frontend for serving through FastAPI:

```powershell
cd frontend\shinobu-chat
npm run build
```

The build is written to `frontend/shinobu-chat/dist/`. When that directory contains `index.html`, FastAPI serves the built frontend at `/`; otherwise `/` returns a message explaining that the frontend has not been built.

## Tests and checks

Run backend tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Run frontend tests and static checks from `frontend/shinobu-chat`:

```powershell
npm test
npm run typecheck
npm run build
```

## Current architecture

- `app/`: FastAPI application, API routes, SQLAlchemy models, schemas, services, event handling, voice pipeline, built-in skills, and Agent orchestration already present on `codex/mvp`.
- `frontend/shinobu-chat/`: React, TypeScript, and Vite client with chat, Live2D, desktop-pet, media, authentication, and API/SSE integration.
- `characters/`: character definitions, including Shinobu's YAML character card.
- `skills/`: user-facing Markdown skill definitions; built-in Python skill implementations live under `app/skills/`.
- `ios/`: iOS integration and appearance references.
- `tests/`: backend unit and integration-oriented tests.
- `docs/`: architecture and agent-maintenance documentation.
- `scripts/`: regenerable report and diagram generation utilities. Their generated files belong in ignored `output/`.

The backend exposes versioned routes under `/api/v1`, persists application data through SQLAlchemy/PostgreSQL, streams chat and synchronization events over SSE, and can serve a compiled frontend from the Vite `dist` directory. This cleanup does not add or redesign Agent functionality.

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
