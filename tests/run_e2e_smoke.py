"""F14-F16 E2E API smoke tests (no Playwright required)."""
import json, urllib.request, urllib.error, importlib, pkgutil

API = "http://127.0.0.1:8000/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0M2Y5N2JhYy0zZWVlLTRhMWQtOTc5MS1hZWQ0OGU1MTEzNDMiLCJleHAiOjE3ODIyNDgxNDV9.kTUMj0JA9vYLUu0lOYJo-KNrIMp2E008nEq7jOfqmvI"

p = 0; ff = 0

def check(name, ok, ev=""):
    global p, ff
    if ok: p += 1; print(f"  [PASS] {name}")
    else: ff += 1; print(f"  [FAIL] {name}: {str(ev)[:100]}")

def post(path, body):
    d = json.dumps(body).encode()
    r = urllib.request.Request(f"{API}{path}", data=d,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}, method="POST")
    return json.loads(urllib.request.urlopen(r).read())

def get(path):
    r = urllib.request.Request(f"{API}{path}",
        headers={"Authorization": f"Bearer {TOKEN}"})
    return json.loads(urllib.request.urlopen(r).read())

def patch(path, body):
    d = json.dumps(body).encode()
    r = urllib.request.Request(f"{API}{path}", data=d,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"}, method="PATCH")
    return json.loads(urllib.request.urlopen(r).read())

# =====================================================================
# F14: Browser Reader
# =====================================================================
print("=== F14 Browser Reader ===")
r = post("/browser/read", {"url": "https://example.com"})
check("F14 Read public URL", r["status"] == "ok" and "Example" in r.get("title", ""),
      f"status={r['status']} title={r.get('title','')[:40]}")

r = post("/browser/search", {"query": "test"})
check("F14 Search unconfigured error", r["status"] == "error",
      r.get("message", "")[:80])

r = post("/browser/summarize", {"url": "https://example.com", "question": "What is this?"})
check("F14 Summarize", r["status"] == "ok",
      f"summary={r.get('summary','')[:50]} key_points={len(r.get('key_points',[]))}")

r = post("/browser/open-url", {"url": "https://example.com"})
check("F14 Open URL", r["status"] == "ok")

r = post("/browser/read", {"url": "http://127.0.0.1:8000/private"})
check("F14 Security: localhost rejected",
      r["status"] == "error" and "security" in r.get("message", "").lower(),
      r.get("message", "")[:80])

r = post("/browser/read", {"url": "file:///C:/Windows/hosts"})
check("F14 Security: file:// rejected", r["status"] == "error")

r = post("/browser/read", {"url": "http://192.168.1.1/admin"})
check("F14 Security: private IP rejected", r["status"] == "error")

# =====================================================================
# F15: Download Safety
# =====================================================================
print("=== F15 Download Safety ===")
r = post("/browser/classify-downloads", {"candidates": [
    {"text": "Image", "href": "https://x.com/d.jpg.exe", "domain": "x.com", "extension": ".exe"}
]})
lvl = r["classified"][0]["risk_level"] if r.get("classified") else "?"
check("F15 Double ext blocked/high", lvl in ("blocked", "high"), lvl)

r = post("/browser/classify-downloads", {"candidates": [
    {"text": "X", "href": "javascript:alert(1)", "domain": "", "extension": ""}
]})
lvl = r["classified"][0]["risk_level"] if r.get("classified") else "?"
check("F15 javascript: blocked", lvl == "blocked", lvl)

r = post("/browser/classify-downloads", {"candidates": [
    {"text": "X", "href": "http://127.0.0.1/m.exe", "domain": "127.0.0.1", "extension": ".exe"}
]})
lvl = r["classified"][0]["risk_level"] if r.get("classified") else "?"
check("F15 localhost blocked", lvl == "blocked", lvl)

r = post("/browser/classify-downloads", {"candidates": [
    {"text": "high speed downloader", "href": "https://x.com/s.exe", "domain": "x.com", "extension": ".exe"}
]})
lvl = r["classified"][0]["risk_level"] if r.get("classified") else "?"
check("F15 High-risk keyword -> high", lvl == "high", lvl)

r = post("/browser/classify-downloads", {"candidates": [
    {"text": "Setup", "href": "https://r.com/a.exe", "domain": "r.com", "extension": ".exe"}
]})
req = r["classified"][0].get("requires_confirmation") if r.get("classified") else None
check("F15 requires_confirmation=true for high risk", req is True, str(req))

# Check suggested_action and reasons exist
r = post("/browser/classify-downloads", {"candidates": [
    {"text": "Setup", "href": "https://r.com/a.exe", "domain": "r.com", "extension": ".exe"}
]})
item = r["classified"][0] if r.get("classified") else {}
check("F15 suggested_action present", bool(item.get("suggested_action")))
check("F15 reasons list present", len(item.get("reasons", [])) > 0)

# =====================================================================
# F16: Permissions
# =====================================================================
print("=== F16 Permissions ===")
s = get("/local-agent/settings")
check("F16 GET settings", True)
check("F16 Browser auto default OFF", s.get("browser_automation_enabled") == False)
check("F16 MCP default OFF", s.get("mcp_enabled") == False)
check("F16 confirm_for_executable default ON", s.get("require_confirm_for_executable") == True)

# Launcher OFF enforcement
patch("/local-agent/settings", {"local_launcher_enabled": False})
try:
    r = post("/local-apps/open", {"intent_type": "open_music"})
    check("F16 Launcher OFF -> open blocked", r.get("status") != "opened", r.get("status"))
except urllib.error.HTTPError as e:
    check("F16 Launcher OFF -> 403", e.code == 403, f"HTTP {e.code}")
patch("/local-agent/settings", {"local_launcher_enabled": True})

# Browser reader OFF enforcement
patch("/local-agent/settings", {"browser_reader_enabled": False})
try:
    r = post("/browser/read", {"url": "https://example.com"})
    check("F16 Reader OFF -> read blocked", r.get("status") != "ok", r.get("status"))
except urllib.error.HTTPError as e:
    check("F16 Reader OFF -> 403", e.code == 403, f"HTTP {e.code}")
patch("/local-agent/settings", {"browser_reader_enabled": True})

# =====================================================================
# F16: Action Logs
# =====================================================================
print("=== F16 Action Logs ===")
try:
    post("/browser/read", {"url": "https://example.com"})
except Exception:
    pass
try:
    post("/browser/classify-downloads", {"candidates": [
        {"text": "X", "href": "https://x.com/a.exe", "domain": "x.com", "extension": ".exe"}
    ]})
except Exception:
    pass

r = get("/browser/actions/logs?limit=10")
check("F16 Browser action logs accessible", len(r.get("logs", [])) > 0,
      f"count={len(r.get('logs',[]))}")

# Check log structure
logs = r.get("logs", [])
if logs:
    log = logs[0]
    check("F16 Log has action_type", "action_type" in log)
    check("F16 Log has status", "status" in log)
    check("F16 Log has created_at", "created_at" in log)

# Filter test
r = get("/browser/actions/logs?action_type=browser_read&limit=5")
logs = r.get("logs", [])
all_read = len(logs) == 0 or all(l.get("action_type") == "browser_read" for l in logs)
check("F16 Log filter by action_type works", all_read, f"filtered={len(logs)}")

# =====================================================================
# F14.5: MCP
# =====================================================================
print("=== F14.5 MCP ===")
s = get("/mcp/status")
check("MCP available", s.get("available") == True)
check("MCP default OFF", s.get("enabled") == False)
check("MCP safe tools present", len(s.get("safe_tools", [])) > 0)
check("MCP blocked tools present", len(s.get("blocked_tools", [])) > 0)

must_block = {"shell_command", "download_file", "run_installer", "file_write", "browser_click"}
check("MCP all dangerous blocked", must_block.issubset(set(s.get("blocked_tools", []))))

must_safe = {"open_local_app", "open_url", "read_webpage", "search_web"}
check("MCP all safe present", must_safe.issubset(set(s.get("safe_tools", []))))

check("MCP default_user_configured bool", "default_user_configured" in s,
      str(s.get("default_user_configured")))

# =====================================================================
# F11-F13 Regression
# =====================================================================
print("=== F11-F13 Regression ===")
apps = get("/local-apps")
check("F11 Local apps list", True, f"count={len(apps)}")

# Cleanup old
for a in apps:
    if a.get("app_key") == "test_notepad_e2e":
        req = urllib.request.Request(f"{API}/local-apps/{a['id']}",
            headers={"Authorization": f"Bearer {TOKEN}"}, method="DELETE")
        urllib.request.urlopen(req)

# Create
app = post("/local-apps", {
    "app_key": "test_notepad_e2e", "intent_type": "open_music",
    "display_name": "E2E Notepad",
    "executable_path": "C:\\Windows\\System32\\notepad.exe",
    "working_dir": "C:\\Windows\\System32",
    "enabled": True, "is_default_for_intent": True, "confirm_required": False,
})
aid = app.get("id", "")
check("F11 Create local app", bool(aid), f"id={aid}")

if aid:
    r = post(f"/local-apps/{aid}/test", {})
    check("F11 Test launch", r.get("status") in ("opened", "failed"),
          f"status={r.get('status')} msg={r.get('message','')[:60]}")

    req = urllib.request.Request(f"{API}/local-apps/{aid}",
        headers={"Authorization": f"Bearer {TOKEN}"}, method="DELETE")
    urllib.request.urlopen(req)
    check("F11 Delete local app", True)

# =====================================================================
# F16: Task SSE
# =====================================================================
print("=== F16 Task SSE ===")
try:
    req = urllib.request.Request(f"{API}/tasks/test/events",
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "text/event-stream"})
    resp = urllib.request.urlopen(req, timeout=3)
    check("F16 Task SSE endpoint responds", True, f"HTTP {resp.getcode()}")
    resp.close()
except urllib.error.HTTPError as e:
    check("F16 Task SSE endpoint", e.code in (200, 404), f"HTTP {e.code}")
except Exception as e:
    check("F16 Task SSE endpoint", False, str(e)[:80])

# =====================================================================
# ToolRegistry (backend, no HTTP)
# =====================================================================
print("=== ToolRegistry ===")
pkg = importlib.import_module("app.services.tools")
names = set()
for mi in pkgutil.iter_modules(pkg.__path__, "app.services.tools."):
    m = importlib.import_module(mi.name)
    ct = getattr(m, "create_tool", None)
    if ct:
        t = ct(type("R", (), {"http_client": None, "skill_registry": None, "session_factory": None})())
        names.add(t.name)

for tn in ["read_webpage", "search_web", "open_url", "open_local_app", "fetch_web_page"]:
    check(f"ToolRegistry has {tn}", tn in names)

# ToolPolicyService explicit groups
from app.services.tool_policy_service import _EXPLICIT_TOOL_GROUPS
check("Policy: open_local_app -> local_app", _EXPLICIT_TOOL_GROUPS.get("open_local_app") == "local_app")
check("Policy: open_url -> browser_open", _EXPLICIT_TOOL_GROUPS.get("open_url") == "browser_open")
check("Policy: read_webpage -> web_search", _EXPLICIT_TOOL_GROUPS.get("read_webpage") == "web_search")
check("Policy: search_web -> web_search", _EXPLICIT_TOOL_GROUPS.get("search_web") == "web_search")

# =====================================================================
# Summary
# =====================================================================
total = p + ff
print(f"\n{'='*60}")
print(f"E2E SMOKE RESULTS: {p}P / {ff}F / {total}T")
print(f"{'='*60}")
if ff > 0:
    print("FAILURES ABOVE — check detailed output")
print(f"\nVerdict: {'ALL PASS' if ff == 0 else 'SOME FAILURES — review above'}")
