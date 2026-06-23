# Phase 2 Architecture Deepening: Explainability & Security Audit

Status: Complete (2026-06-24)
Branch: codex/mvp

## Overview

Phase 2 deepens the architecture from "feature MVP" to "maintainable, explainable, product-ready Agent platform" by adding:

1. **PromptTrace** — per-message context metadata for explainability
2. **ActionAuditLog** — unified audit trail across all action sources
3. **ToolRegistry audit** — every tool execution recorded
4. **MCP audit** — server-level rejections recorded
5. **Browser/Download audit** — browser actions and download classification recorded
6. **Download risk hardening** — formalized risk decisions, hard blocklist cannot be overridden
7. **Debug API** — authorized inspection endpoints
8. **Frontend panels** — ActionAuditPanel for debugging

## PromptTrace Design

Each user message writes one PromptTrace record containing:
- Route mode / conversation mode
- SHA-256 hashes of cache zones (pinned prefix, character card, tool catalog, skill catalog)
- Memory IDs retrieved this turn
- Activated skill names
- Context injection flags (vision, persona, emotion, browser, MCP)
- Router reason and context summary

**Never stored**: system prompt text, tool schemas, full web page content, API keys.

## ActionAuditLog Design

Unified audit model replacing fragmented BrowserActionLog + LocalActionLog patterns.

| Field | Purpose |
|-------|---------|
| source | tool / browser / local_agent / mcp / download / task |
| action_type | e.g. browser_read, open_local_app, classify_download |
| risk_level | blocked / high / medium / low / trusted / unknown |
| policy_allowed | Was the action allowed by ToolPolicyService? |
| verified | Did post-execution verification pass? |
| arguments_redacted | Tool arguments with secrets removed |
| result_summary | Truncated result, never full content |

### Audit integration points

| Source | When | What |
|--------|------|------|
| Tool | execute_verified() | Policy denied + executed + verified |
| Browser | Every facade method | Read, search, summarize, open-url |
| Download | classify_downloads() | Per-candidate risk decision |
| MCP | Server-level rejection | Blocked tool, not in safe list, no user |

## Download Risk Hardening

`DownloadRiskDecision` formalizes the three-layer classification:

1. **Hard blocklist** (CANNOT be overridden): javascript://, 127.0.0.1, localhost, .jpg.exe, private IPs
2. **Trusted source**: can lower risk but never override hard block
3. **LLM advisory**: informational only

`hard_blocked=True` always produces `risk_level=blocked` and `policy_allowed=False`, regardless of trusted source status.

## Debug API

All endpoints require authentication and user isolation:

| Endpoint | Purpose |
|----------|---------|
| GET /debug/prompt-traces/conversations/{id} | List traces for conversation |
| GET /debug/prompt-traces/messages/{id} | Get trace for message |
| GET /debug/action-audits | List audits (filterable by source) |
| GET /debug/action-audits/{id} | Get single audit |
| GET /debug/action-audits/conversations/{id} | List audits by conversation |
| GET /debug/action-audits/messages/{id} | List audits by message |

## Sensitive Information Constraints

- ActionAuditService.redact_payload() strips api_key, token, password, secret fields
- PromptTrace never stores system prompt content
- No full web page content in audit records
- Debug API enforces user_id isolation

## Known Limitations / Phase 1 TODOs

- MemoryAgent.search() returns text-only results; memory_ids is [] until MemoryAgent.search_hits() is implemented
- tool_names_available in PromptTrace is empty until AgentCoordinator renders tool catalog into the trace
- pinned_prefix_sha / character_card_sha / tool_catalog_sha / skill_catalog_sha are empty until PrefixCacheManager is wired into the trace path

## File Changes

### New Files
- app/models/action_audit_log.py
- app/models/prompt_trace.py
- app/services/action_audit_service.py
- app/services/prompt_trace_service.py
- app/schemas/action_audit.py
- app/schemas/debug_trace.py
- app/api/v1/routes/debug.py
- frontend/shinobu-chat/src/api/debug.ts
- frontend/shinobu-chat/src/debug/ActionAuditPanel.tsx
- docs/architecture/phase2-explainability-security-after-f14-f16.md

### Modified Files
- app/models/__init__.py — registered ActionAuditLog, PromptTrace
- app/db/init_db.py — added ensure_phase2_columns()
- app/services/agents/coordinator.py — AgentPlan + trace_context
- app/services/turn/conversation_turn_service.py — PromptTrace write
- app/services/tool_registry.py — execute_verified() + audit
- app/services/browser/browser_facade_service.py — ActionAudit in all methods
- app/services/download_risk_classifier.py — DownloadRiskDecision + hard block hardening
- app/mcp/server.py — MCP rejection audit
- app/api/v1/api.py — registered debug router
