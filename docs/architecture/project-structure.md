# ShinobuChat Project Structure

## 1. Overview

ShinobuChat uses a layered architecture:

- **API layer** (`app/api/`) — FastAPI routes, middleware, dependencies
- **Domain layer** (`app/domains/`) — business logic organized by domain
- **Core infrastructure** (`app/core/`) — config, exceptions, security, rate limiting, URL/image validation
- **Persistence layer** (`app/db/`, `app/models/`, `app/schemas/`) — database session, ORM models, Pydantic schemas
- **Integrations layer** (`app/integrations/`) — HTTP client, SSE, event streams
- **Skills system** (`app/skills/`) — skill registry and builtin skills
- **MCP entry** (`app/mcp/`) — MCP server compatibility wrapper
- **Frontend features** (`frontend/shinobu-chat/src/features/`) — feature-based UI modules
- **Compatibility layer** (`app/services/`) — re-export wrappers for old import paths

## 2. Backend Layout

```
app/
  api/              # FastAPI routes (stable, not moved)
    deps.py         # Shared dependencies (get_db, get_current_user_id, etc.)
    v1/
      api.py        # APIRouter aggregation
      routes/       # Individual route modules (/api/v1/*)
        auth.py, users.py, conversations.py, messages.py,
        browser.py, local_agent.py, mcp.py, tasks.py, debug.py,
        config.py, memories.py, todos.py, reminders.py, goals.py,
        skills.py, skill_market.py, modes.py, persona.py, voice.py,
        vision.py, live2d.py, diaries.py, sync.py, ...

  core/             # Shared infrastructure (no domain imports)
    config.py       # App settings from environment
    exceptions.py   # Custom exception classes
    rate_limiter.py # Rate limiting middleware
    time.py         # Timezone/normalization helpers
    url_validation.py     # URL safety checks
    image_validation.py   # Image upload safety checks
    security/
      redaction.py  # Secret/key redaction

  db/               # Database layer
    session.py      # SQLAlchemy session factory
    init_db.py      # Table creation
    migrations.py   # Schema migrations

  models/           # SQLAlchemy ORM models (centralized, not split by domain)
    __init__.py, user.py, message.py, conversation.py, ...

  schemas/          # Pydantic request/response schemas (centralized)
    __init__.py, auth.py, browser.py, message.py, ...

  domains/          # Business logic organized by domain (NEW in Phase 4)
    chat/           # Message sending, conversation turns
    agent/          # Agent orchestration, behavior engine
    browser/        # Web search, reading, summarization, download safety
    local_agent/    # Local app control, permission settings
    mcp/            # MCP server, tool adapter
    tasks/          # Background task tracking (SSE events)
    jobs/           # Scheduled jobs (reminders, goals, diary)
    capabilities/   # Capability registration and policy enforcement
    observability/  # Prompt traces, action audits, skill run logs
    memory/         # Long-term memory / embedding (future)
    skills/         # Skill management (future)
    planning/       # Todos, goals, reminder scheduling (future)
    diary/          # Diary generation (future)
    persona/        # Character/persona settings (future)
    voice/          # TTS/ASR (future)
    vision/         # Image understanding (future)
    live2d/         # Live2D avatar (future)
    sync/           # Cross-device sync (future)

  integrations/     # External integrations
    http/           # HTTP client
    events/         # Stream events, SSE helpers

  mcp/              # MCP compat wrappers (delegates to domains/mcp)
  services/         # Compatibility wrappers for old import paths
  skills/           # Skill registry and builtin skills
  seed/             # Seed data (default skills)
  events/           # Internal event bus
```

## 3. Domain Boundaries

| Domain | Responsibility | Key Files |
|---|---|---|
| **chat** | Message sending, turn management, reply generation | message_service.py, turn/* |
| **agent** | Agent orchestration, routing, behavior decisions | agent_orchestrator.py, behavior_engine.py, agents/* |
| **browser** | Web search, reading, summarization, download safety | browser_facade_service.py, web_reader_service.py, download/* |
| **local_agent** | Local app control, permission toggles | local_app_service.py, local_agent_settings_service.py |
| **mcp** | MCP protocol server, tool registration | server.py, tool_adapter.py |
| **tasks** | Background task progress tracking via SSE | task_event_store.py, task_event_service.py, task_run_service.py |
| **jobs** | Scheduled background jobs | job_scheduler.py, reminder_scan_job.py, goal_checkin_job.py |
| **capabilities** | Feature flag / capability gating | capability_registry.py, capability_policy_service.py |
| **observability** | Debug traces, audit logs, skill run history | prompt_trace_service.py, action_audit_service.py, skill_run_log_service.py |

## 4. Import Rules

- **New backend code** should import from `app.domains.*`
- **`app.services.*`** is kept as compatibility wrappers only
- **API routes** may call domain services or facades directly
- **Domains** must not import API routes
- **`app/core/`** must not import from domains
- **`app/models/`** and **`app/schemas/`** remain centralized (not split by domain)
- **Database table names** must not change
- **SSE event names** must not change
- **API paths** must not change

### Import Path Mapping (Phase 4 Migration)

| Old Path | New Path |
|---|---|
| `app.services.browser.browser_facade_service` | `app.domains.browser.browser_facade_service` |
| `app.services.browser.browser_action_log_service` | `app.domains.browser.logs.browser_action_log_service` |
| `app.services.browser.trusted_download_source_service` | `app.domains.browser.trusted_sources.trusted_download_source_service` |
| `app.services.browser_automation_service` | `app.domains.browser.browser_automation_service` |
| `app.services.web_reader_service` | `app.domains.browser.web_reader_service` |
| `app.services.web_search_service` | `app.domains.browser.web_search_service` |
| `app.services.web_summarizer_service` | `app.domains.browser.web_summarizer_service` |
| `app.services.download_service` | `app.domains.browser.download.download_service` |
| `app.services.download_candidate_extractor` | `app.domains.browser.download.download_candidate_extractor` |
| `app.services.download_risk_classifier` | `app.domains.browser.download.download_risk_classifier` |
| `app.services.local_agent_settings_service` | `app.domains.local_agent.local_agent_settings_service` |
| `app.services.local_app_service` | `app.domains.local_agent.local_app_service` |
| `app.mcp.server` | `app.domains.mcp.server` |
| `app.mcp.config` | `app.domains.mcp.config` |
| `app.mcp.tool_adapter` | `app.domains.mcp.tool_adapter` |
| `app.services.tasks.task_event_store` | `app.domains.tasks.task_event_store` |
| `app.services.tasks.task_event_service` | `app.domains.tasks.task_event_service` |
| `app.services.tasks.task_run_service` | `app.domains.tasks.task_run_service` |
| `app.services.jobs.*` | `app.domains.jobs.*` |
| `app.services.behavior_engine` | `app.domains.agent.behavior_engine` |
| `app.services.capabilities.*` | `app.domains.capabilities.*` |
| `app.services.action_audit_service` | `app.domains.observability.action_audit_service` |
| `app.services.prompt_trace_service` | `app.domains.observability.prompt_trace_service` |
| `app.services.skill_run_log_service` | `app.domains.observability.skill_run_log_service` |

## 5. Frontend Layout

```
src/
  main.tsx          # React entry point
  App.tsx           # Root component (uses feature barrel imports)

  api/              # API client modules (centralized, not split by feature)
    client.ts, sse.ts, browser.ts, debug.ts, ...

  features/         # Feature-based UI modules (NEW in Phase 4)
    chat/           # Chat UI: MessageList, Composer, ConversationList, useChatStream
    live2d/         # Live2D avatar stage
    settings/       # Settings page, config panels
    debug/          # Debug panels: audits, job runs, task runs
    reminders/      # Reminder bubble UI
    goals/          # Goal tracker
    browser/        # Browser reader/search/summary UI
    local-agent/    # Local app action UI
    mcp/            # MCP settings
    diaries/        # Diary panel
    memories/       # Memory timeline
    modes/          # Mode switch
    desktop-pet/    # Desktop pet taskbar

  hooks/            # Shared React hooks
  types/            # Shared TypeScript types (future split)
  utils/            # Shared utilities
```

Each feature directory has:
- `index.ts` — barrel export (re-exports components for clean imports)
- `components/` — feature-specific React components
- `hooks/` — feature-specific React hooks

## 6. Migration Notes (Phase 4)

### Completed Migrations

- **Browser/Download/Web** domain: 10 files moved to `app/domains/browser/`
- **Local Agent** domain: 2 files moved to `app/domains/local_agent/`
- **MCP** domain: 3 files moved to `app/domains/mcp/`
- **Tasks** domain: 3 files moved to `app/domains/tasks/`
- **Jobs** domain: 7 files moved to `app/domains/jobs/`
- **Capabilities** domain: 2 files moved to `app/domains/capabilities/`
- **BehaviorEngine**: moved to `app/domains/agent/behavior_engine.py`
- **Observability** domain: 3 files moved to `app/domains/observability/`
- **Frontend**: feature barrel exports created, App.tsx updated
- **Docs**: organized into architecture/progress/coursework/archive

### Compatibility Wrappers Preserved

All old `app/services/*` paths have been converted to compatibility wrappers that re-export from `app.domains.*`. Old import paths continue to work.

### Deferred (High Risk)

The following were deferred due to high risk of circular imports or API breakage:

- `app/services/message_service.py` → `app/domains/chat/`
- `app/services/turn/*` → `app/domains/chat/turn/`
- `app/services/agent_orchestrator.py` → `app/domains/agent/`
- `app/services/agents/*` → `app/domains/agent/agents/`
- `app/services/tool_registry.py` → `app/domains/agent/tools/`
- `app/services/tool_policy_service.py` → `app/domains/agent/tools/`
- `app/services/tool_verifier.py` → `app/domains/agent/tools/`
- `app/services/tools/*` → `app/domains/agent/tools/builtin/`
- `app/services/ai_client.py` — used by many modules, needs careful migration
- Remaining standalone services in `app/services/` (voice, vision, sync, etc.)

These can be migrated in a future Phase 5 after more test coverage is added.

### Remaining Cleanup

- Remove duplicate docs at old paths (originals kept for reference)
- Clean up empty component directories in features/ that only have barrel exports
- Migrate remaining services to appropriate domains
- Add `rewrite_imports.py` to CI/pre-commit
