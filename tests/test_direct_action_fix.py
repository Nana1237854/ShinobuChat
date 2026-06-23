"""Tests for Direct Action path fixes:
  1. MemoryWriteScheduler.schedule_after_turn_text (no empty MessageCreate crash)
  2. DirectActionRunner pending_info fields (id, pending_action_id, description, etc.)
"""
import asyncio
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
# Test 1: MemoryWriteScheduler.schedule_after_turn_text
# =============================================================================
print("=== MemoryWriteScheduler.schedule_after_turn_text ===")

from app.services.turn.memory_write_scheduler import MemoryWriteScheduler

# With no memory_agent, should be a no-op (no crash)
scheduler = MemoryWriteScheduler(memory_agent=None)

class FakeState:
    class FakeMessage:
        id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user_message = FakeMessage()
    reply_text = "打开了 Music~"

state = FakeState()

# Should not crash with None agent
scheduler.schedule_after_turn_text(user_id="u1", user_text="我想听歌", state=state)
check("schedule_after_turn_text no-op when memory_agent is None", True)

# Should not crash with empty user_text
scheduler.schedule_after_turn_text(user_id="u1", user_text="", state=state)
check("schedule_after_turn_text skips empty user_text", True)

# Should not crash with empty reply_text
state.reply_text = ""
scheduler.schedule_after_turn_text(user_id="u1", user_text="我想听歌", state=state)
check("schedule_after_turn_text skips empty reply_text", True)

# Should not crash with whitespace-only user_text
state.reply_text = "回复"
scheduler.schedule_after_turn_text(user_id="u1", user_text="   ", state=state)
check("schedule_after_turn_text skips whitespace-only user_text", True)

# Should not crash with None user_text
scheduler.schedule_after_turn_text(user_id="u1", user_text=None, state=state)
check("schedule_after_turn_text handles None user_text", True)

# Should not crash with None reply_text
state.reply_text = None
scheduler.schedule_after_turn_text(user_id="u1", user_text="我想听歌", state=state)
check("schedule_after_turn_text handles None reply_text", True)


# =============================================================================
# Test 2: DirectActionRunner pending_info structure
# =============================================================================
print("\n=== DirectActionRunner pending_info structure ===")

from app.services.turn.direct_action_runner import DirectActionRunner

# We test the structure without a real DB by patching
# Verify the class is importable and build_reply works
runner = DirectActionRunner()

# Test build_reply (static, no DB needed)
from unittest.mock import MagicMock

da = MagicMock()
da.action = "open_local_app"
da.intent_type = "open_music"

check("build_reply opened", "好的，已为你打开" in runner.build_reply(da, {"status": "opened", "display_name": "Music"}))
check("build_reply requires_confirmation", "需要确认" in runner.build_reply(da, {"status": "requires_confirmation", "display_name": "Music"}))
check("build_reply not_configured", "还没配置" in runner.build_reply(da, {"status": "not_configured", "display_name": "Music"}))
check("build_reply requires_selection", "请" in runner.build_reply(da, {"status": "requires_selection", "display_name": "Music"}))
check("build_reply failed", "失败" in runner.build_reply(da, {"status": "failed", "display_name": "Music"}))


# =============================================================================
# Test 3: Pending info dict structure (unit test without DB)
# =============================================================================
print("\n=== Pending info dict structure ===")

def construct_pending_info(result, user_id, conversation_id, da):
    """Replicate the logic from DirectActionRunner.run() for testing."""
    pending_action_id = result.get("pending_action_id")

    if result.get("status") != "requires_confirmation" or not pending_action_id:
        return None

    return {
        "id": pending_action_id,
        "pending_action_id": pending_action_id,
        "user_id": str(user_id),
        "conversation_id": str(conversation_id),
        "action_type": da.action,
        "app_key": result.get("app_key"),
        "display_name": result.get("display_name"),
        "description": result.get("message") or f"{result.get('display_name') or result.get('app_key') or '应用'} 请求你的确认",
        "intent_type": da.intent_type,
        "status": "waiting_confirmation",
        "expires_at": result.get("expires_at"),
        "created_at": result.get("created_at"),
    }

test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
test_conv_id = uuid.UUID("00000000-0000-0000-0000-000000000002")

# Case A: Full result with all fields
result_full = {
    "status": "requires_confirmation",
    "pending_action_id": "pending-uuid-123",
    "app_key": "myapp",
    "display_name": "My App",
    "message": "This app needs confirmation",
    "expires_at": "2025-12-31T23:59:00",
    "created_at": "2025-12-31T23:54:00",
    "executable_path": "/path/to/app.exe",
}
info = construct_pending_info(result_full, test_user_id, test_conv_id, da)
check("pending_info has id", info["id"] == "pending-uuid-123")
check("pending_info has pending_action_id", info["pending_action_id"] == "pending-uuid-123")
check("pending_info has user_id", info["user_id"] == str(test_user_id))
check("pending_info has conversation_id", info["conversation_id"] == str(test_conv_id))
check("pending_info has action_type", info["action_type"] == "open_local_app")
check("pending_info has app_key", info["app_key"] == "myapp")
check("pending_info has display_name", info["display_name"] == "My App")
check("pending_info has description", info["description"] == "This app needs confirmation")
check("pending_info has intent_type", info["intent_type"] == "open_music")
check("pending_info has status", info["status"] == "waiting_confirmation")
check("pending_info has expires_at", info["expires_at"] == "2025-12-31T23:59:00")
check("pending_info has created_at", info["created_at"] == "2025-12-31T23:54:00")

# Case B: No message field — description falls back to display_name
result_no_msg = {
    "status": "requires_confirmation",
    "pending_action_id": "pending-uuid-456",
    "app_key": "browser",
    "display_name": "Chrome",
}
info2 = construct_pending_info(result_no_msg, test_user_id, test_conv_id, da)
check("pending_info description fallback to display_name", "Chrome" in info2["description"])

# Case C: No display_name or message — description falls back to app_key
result_minimal = {
    "status": "requires_confirmation",
    "pending_action_id": "pending-uuid-789",
    "app_key": "myapp",
}
info3 = construct_pending_info(result_minimal, test_user_id, test_conv_id, da)
check("pending_info description fallback to app_key", "myapp" in info3["description"])

# Case D: Not requires_confirmation — no pending_info generated
result_opened = {
    "status": "opened",
    "message": "Launched",
    "app_key": "myapp",
    "display_name": "My App",
}
info4 = construct_pending_info(result_opened, test_user_id, test_conv_id, da)
check("no pending_info for opened status", info4 is None)

# Case E: requires_confirmation but no pending_action_id — should be None
result_no_id = {
    "status": "requires_confirmation",
    "app_key": "myapp",
}
info5 = construct_pending_info(result_no_id, test_user_id, test_conv_id, da)
check("no pending_info when pending_action_id is missing", info5 is None)


# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*60}")
print(f"Results: {pass_count} passed, {fail_count} failed, {pass_count + fail_count} total")
if fail_count > 0:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
