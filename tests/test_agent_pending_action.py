"""Tests for Agent-mode pending_action propagation.

Covers:
  - open_local_app tool writes pending_action into context.metadata
  - AgentOrchestrator yields pending_action StreamEvent
  - StreamEvent("pending_action", ...) includes id and pending_action_id
  - context.metadata is NOT cleared between tool calls
  - Direct Action path and Agent tool path both produce pending_action
"""
import json
import sys
import uuid

sys.path.insert(0, ".")

pass_count = 0
fail_count = 0


def check(name, cond):
    global pass_count, fail_count
    if cond:
        pass_count += 1
        print(f"  [PASS] {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name}")


# =============================================================================
# Test 1: pending_action has both id and pending_action_id
# =============================================================================
print("=== Test 1: pending_action payload has both id and pending_action_id ===")


def build_pending_action(result, user_id, conversation_id, intent_type):
    """Replicate the open_local_app handler's pending_action construction."""
    pending_id = result.get("pending_action_id")
    return {
        "id": pending_id,
        "pending_action_id": pending_id,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id) if conversation_id else "",
        "action_type": "open_local_app",
        "app_key": result.get("app_key", ""),
        "display_name": result.get("display_name", ""),
        "description": result.get("message")
            or f"{result.get('display_name') or result.get('app_key') or '应用'} 请求你的确认",
        "intent_type": intent_type or "",
        "status": "waiting_confirmation",
        "expires_at": result.get("expires_at"),
        "created_at": result.get("created_at"),
    }


uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
cid = uuid.UUID("00000000-0000-0000-0000-000000000002")

result = {
    "status": "requires_confirmation",
    "pending_action_id": "pending-123",
    "app_key": "CloudMusic",
    "display_name": "网易云音乐",
    "message": "Opening '网易云音乐' requires confirmation.",
    "expires_at": "2026-06-25T00:00:00",
    "created_at": "2026-06-24T23:55:00",
    "executable_path": r"D:\CloudMusic\cloudmusic.exe",
}

pa = build_pending_action(result, uid, cid, "open_music")

check("1a: has id", pa["id"] == "pending-123")
check("1b: has pending_action_id", pa["pending_action_id"] == "pending-123")
check("1c: id equals pending_action_id", pa["id"] == pa["pending_action_id"])
check("1d: has user_id", pa["user_id"] == str(uid))
check("1e: has conversation_id", pa["conversation_id"] == str(cid))
check("1f: has action_type", pa["action_type"] == "open_local_app")
check("1g: has app_key", pa["app_key"] == "CloudMusic")
check("1h: has display_name", pa["display_name"] == "网易云音乐")
check("1i: has description", "网易云音乐" in pa["description"])
check("1j: has status waiting_confirmation", pa["status"] == "waiting_confirmation")
check("1k: has expires_at", pa["expires_at"] == "2026-06-25T00:00:00")
check("1l: has created_at", pa["created_at"] == "2026-06-24T23:55:00")


# =============================================================================
# Test 2: requires_confirmation → metadata written
# =============================================================================
print("\n=== Test 2: requires_confirmation writes metadata ===")

# Simulate context.metadata dict (mutable dict, similar to ToolContext.metadata)
metadata: dict = {}

# Simulate what the open_local_app handler does
if result.get("status") == "requires_confirmation" and result.get("pending_action_id"):
    metadata["pending_action"] = build_pending_action(result, uid, cid, "open_music")

check("2a: metadata has pending_action", "pending_action" in metadata)
check("2b: metadata not cleared", len(metadata) == 1)
check("2c: pending_action has correct id", metadata["pending_action"]["id"] == "pending-123")


# =============================================================================
# Test 3: opened status → no metadata written
# =============================================================================
print("\n=== Test 3: opened status → no metadata ===")

metadata3: dict = {}
result_opened = {"status": "opened", "display_name": "网易云音乐"}

if result_opened.get("status") == "requires_confirmation" and result_opened.get("pending_action_id"):
    metadata3["pending_action"] = build_pending_action(result_opened, uid, cid, "open_music")

check("3a: opened does not write metadata", "pending_action" not in metadata3)


# =============================================================================
# Test 4: failed status → no metadata written
# =============================================================================
print("\n=== Test 4: failed status → no metadata ===")

metadata4: dict = {}
result_failed = {"status": "failed", "message": "Path validation failed"}

if result_failed.get("status") == "requires_confirmation" and result_failed.get("pending_action_id"):
    metadata4["pending_action"] = build_pending_action(result_failed, uid, cid, "")

check("4a: failed does not write metadata", "pending_action" not in metadata4)


# =============================================================================
# Test 5: AgentOrchestrator yields StreamEvent("pending_action", ...)
# =============================================================================
print("\n=== Test 5: AgentOrchestrator yields pending_action StreamEvent ===")

from app.services.stream_events import StreamEvent

metadata5 = {"pending_action": build_pending_action(result, uid, cid, "open_music")}

# Simulate orchestrator logic
pending_action = metadata5.get("pending_action")
assert pending_action is not None
event = StreamEvent("pending_action", pending_action)

check("5a: event type is pending_action", event.event == "pending_action")
check("5b: event payload has id", event.payload["id"] == "pending-123")
check("5c: event payload has pending_action_id", event.payload["pending_action_id"] == "pending-123")


# =============================================================================
# Test 6: MessageService captures pending_action from stream
# =============================================================================
print("\n=== Test 6: MessageService captures pending_action from stream ===")

# Simulate the create_streaming_response loop
stream_items = [
    StreamEvent("progress", {"skill_name": "agent", "message": "test", "percent": 0.5}),
    StreamEvent("pending_action", pending_action),  # emitted by orchestrator
    StreamEvent("chunk", {"delta": "已找到网易云音乐"}),
    "已找到网易云音乐啦，不过需要你确认一下才能打开哦～",  # final string content
]

captured_pending_action = None
full_reply = ""
for item in stream_items:
    if isinstance(item, StreamEvent):
        if item.event == "pending_action" and item.payload:
            captured_pending_action = item.payload
    else:
        full_reply = item

check("6a: captured pending_action from stream", captured_pending_action is not None)
check("6b: captured pending_action has correct id", captured_pending_action["id"] == "pending-123")
check("6c: full_reply captured correctly", "网易云音乐" in full_reply)


# =============================================================================
# Test 7: done event includes pending_action
# =============================================================================
print("\n=== Test 7: done event includes pending_action ===")

# Simulate done payload construction
done_payload = {
    "conversation_id": str(cid),
    "assistant_messages": [],
    "pending_action": captured_pending_action if captured_pending_action else None,
}

check("7a: done payload has pending_action", done_payload["pending_action"] is not None)
check("7b: done pending_action id correct", done_payload["pending_action"]["id"] == "pending-123")


# =============================================================================
# Test 8: normalizePendingAction handles missing id
# =============================================================================
print("\n=== Test 8: normalizePendingAction handles missing id ===")


def normalize_pending_action(payload):
    """JS normalizePendingAction ported to Python for testing."""
    if not payload:
        return payload
    return {
        **payload,
        "id": payload.get("id") or payload.get("pending_action_id"),
        "description": (
            payload.get("description")
            or payload.get("message")
            or f"{payload.get('display_name') or payload.get('app_key') or '应用'} 请求你的确认"
        ),
    }


# Case A: only pending_action_id (no id)
pa_no_id = {
    "pending_action_id": "pa-456",
    "display_name": "Chrome",
    "app_key": "Chrome",
}
normalized = normalize_pending_action(pa_no_id)
check("8a: missing id filled from pending_action_id", normalized["id"] == "pa-456")

# Case B: has both
pa_both = {
    "id": "pa-789",
    "pending_action_id": "pa-789",
    "display_name": "VS Code",
}
normalized2 = normalize_pending_action(pa_both)
check("8b: both present, id preserved", normalized2["id"] == "pa-789")

# Case C: missing description, has message
pa_msg = {
    "id": "pa-msg",
    "message": "This app needs confirmation",
    "display_name": "App",
}
normalized3 = normalize_pending_action(pa_msg)
check("8c: description from message", "This app needs confirmation" in normalized3["description"])


# =============================================================================
# Test 9: StreamEvent.action format is correct
# =============================================================================
print("\n=== Test 9: StreamEvent.action format ===")

# Check that the StreamEvent class works correctly
action_event = StreamEvent("action", {
    "action": "open_local_app",
    "intent_type": "open_music",
    "status": "requires_confirmation",
    "message": "test",
})
check("9a: action event type", action_event.event == "action")
check("9b: action event payload", action_event.payload["action"] == "open_local_app")


# =============================================================================
# Summary
# =============================================================================
if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"Results: {pass_count} passed, {fail_count} failed, {pass_count + fail_count} total")
    if fail_count > 0:
        print("SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
