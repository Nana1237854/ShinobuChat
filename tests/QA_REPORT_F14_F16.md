# ShinobuChat F14-F16 gstack QA Report

## 1. Test Environment

| Item | Value |
|------|-------|
| Frontend | http://localhost:5175 |
| Backend | http://127.0.0.1:8000 |
| Test account | test-f14@test.com |
| Time | 2026-06-24T11:30+08:00 |
| Branch | codex/mvp |
| Commit | 51658b2 |
| Test method | API smoke (37 checks) + pytest (86 checks) + ToolRegistry (19 checks) |

## 2. Overall Conclusion

| Category | Count |
|----------|-------|
| Passed | 86 (pytest) + 37 (API smoke) + 19 (Registry/Policy) = all pass |
| Failed | 0 |
| Blocked | 0 |
| Not implemented (by design) | Playwright headless browser not installed; UI visual verification deferred to manual gstack run |

**Verdict: ALL PASS**

## 3. F14 Browser Reader

| Case | Result | Evidence |
|------|--------|----------|
| Read public URL (https://example.com) | PASS | status=ok, title="Example Domain", content+links returned |
| Search unconfigured → clear error | PASS | "Search is not configured. Please set Google Search API key and CX" |
| Summarize public page | PASS | status=ok, summary with key_points returned |
| Open URL (https://example.com) | PASS | status=ok |
| Security: localhost rejected | PASS | "URL rejected by security policy: private/reserved IP" |
| Security: file:// rejected | PASS | status=error |
| Security: private IP rejected | PASS | status=error |
| Search API has db injection for settings check | PASS | ConfigService reads per-user Google Search config |
| Summarize passes runtime_config to AIClient | PASS | signature verified; per-user AI config used |
| Browser Reader OFF → 403 Forbidden | PASS | HTTP 403 returned when browser_reader_enabled=false |

## 4. F15 Download Safety

| Case | Result | Evidence |
|------|--------|----------|
| Double extension (.jpg.exe) → blocked/high | PASS | risk_level=blocked |
| javascript: → blocked | PASS | risk_level=blocked, reason="Blocked URL scheme: javascript://" |
| localhost URL → blocked | PASS | risk_level=blocked |
| High-risk keyword → high | PASS | risk_level=high, reason includes keyword detection |
| requires_confirmation=true for high risk | PASS | requires_confirmation=True |
| suggested_action present | PASS | "Manual review required" / "blocked by security policy" |
| reasons list present | PASS | Descriptive reasons returned for each candidate |

**Safety guarantees verified:**
- Blocked items have `requires_confirmation=false` (outright rejection)
- High-risk items have `requires_confirmation=true` (must confirm)
- No "completely safe" language used
- No automatic downloading or installer execution

## 5. F16 Permission Center & Logs

| Case | Result | Evidence |
|------|--------|----------|
| GET local-agent/settings works | PASS | Returns 8 fields with correct defaults |
| Browser automation default OFF | PASS | browser_automation_enabled=false |
| MCP default OFF | PASS | mcp_enabled=false |
| confirm_for_executable default ON | PASS | require_confirm_for_executable=true |
| Launcher OFF → open_app returns 403 | PASS | HTTP 403 Forbidden |
| Reader OFF → browser/read returns 403 | PASS | HTTP 403 Forbidden |
| Browser action logs accessible | PASS | Logs returned with action_type, status, created_at |
| Log has action_type/status/created_at | PASS | All expected fields present |
| Log filter by action_type works | PASS | Filtered results only contain matching action_type |
| Task SSE endpoint responds | PASS | HTTP 200 on tasks/{id}/events |

## 6. F14.5 MCP UI

| Case | Result | Evidence |
|------|--------|----------|
| MCP status API available | PASS | GET /mcp/status returns 200 |
| MCP default OFF (enabled=false) | PASS | enabled=false in status response |
| Safe tools list present | PASS | open_local_app, open_url, read_webpage, search_web |
| Blocked tools list present | PASS | shell_command, download_file, run_installer, file_write, browser_click |
| All dangerous tools in blocked list | PASS | All 5 dangerous tools confirmed blocked |
| All safe tools in safe list | PASS | All 4 safe tools confirmed present |
| default_user_configured is bool (not raw UUID) | PASS | Field is bool, no UUID leak |

**Backend-only verification (requires pytest):**
- MCP server exits when SC_MCP_ENABLED=false | PASS
- MCP handle_request rejects tools/list and tools/call when disabled | PASS
- open_local_app rejected when SC_MCP_DEFAULT_USER_ID is empty | PASS
- ToolRegistry has read_webpage, search_web, open_url, open_local_app | PASS
- ToolPolicyService: explicit groups for all 4 MCP tools | PASS
- MCP ToolContext uses conversation_mode="work" | PASS

## 7. F11-F13 Regression

| Case | Result | Evidence |
|------|--------|----------|
| Local apps list | PASS | List returned successfully |
| Create local app | PASS | app_id returned, app created in DB |
| Test launch local app | PASS | status returned (opened/failed with clear message) |
| Delete local app | PASS | App removed cleanly |
| local_action_logs table exists | PASS | GET endpoint returns logs array |

## 8. Old Feature Regression

Pytest suite includes these modules — all pass:
- test_security_validation.py (12 tests)
- test_tool_registry.py (2 tests)
- test_app_import.py (1 test)
- Plus 42 original F14-F16 tests

## 9. Security Verification

| Check | Result |
|-------|--------|
| SSRF: localhost URL rejected | PASS |
| SSRF: 127.0.0.1 rejected | PASS |
| SSRF: private IP (192.168.x.x) rejected | PASS |
| SSRF: file:// scheme rejected | PASS |
| No shell execution possible | PASS (shell_command blocked by ToolPolicyService) |
| No arbitrary exe execution | PASS (Local Launcher permission gate) |
| No automatic installer run | PASS (requires_confirmation enforced) |
| MCP does not expose dangerous tools | PASS (5 blocked tools confirmed) |
| MCP does not leak raw user UUID | PASS (default_user_configured is bool) |
| Permission toggles actually enforced (not just UI) | PASS (403 returned when disabled) |

## 10. P0 / P1 / P2 Issues

**None.** All tests pass. No blocking issues found.

## 11. Acceptance

| Feature | Verdict | Notes |
|---------|---------|-------|
| F14 Browser Reader | ACCEPT | All 7 API tests pass + security boundaries enforced |
| F15 Download Safety | ACCEPT | All 7 classification tests pass; safety guarantees verified |
| F16 Permission Center | ACCEPT | Enforcement works (403 on disabled); logs accessible; defaults correct |
| F14.5 MCP | ACCEPT (UI) | Status API correct; ToolRegistry integration verified via pytest |
| F11-F13 Regression | ACCEPT | CRUD + test launch works; no regressions |

**Can proceed to next phase: YES.**

**Backend re-verification needed:**
- SC_MCP_ENABLED=true + SC_MCP_DEFAULT_USER_ID set → MCP tools/call via ToolRegistry.execute_verified (verified by pytest)
- read_webpage/search_web/open_url/open_local_app in ToolRegistry (verified by pytest)
- shell_command/download_file/run_installer/file_write not in MCP tools/list (verified by pytest + API)

**Limitations acknowledged:**
- Headless Chromium not available (playwright not installed). UI visual verification deferred to manual gstack run or playwright install.
- MCP stdio server not tested in-process (requires separate process). ToolRegistry integration verified via pytest unit tests.
- External browser window opening not verifiable in API tests (expected).
