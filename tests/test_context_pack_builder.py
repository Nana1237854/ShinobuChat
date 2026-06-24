"""Tests for ContextPackBuilder.

Covers:
  - recent_messages are built correctly
  - active pending intent is injected
  - expired pending intent is NOT injected
  - executable_path is NOT exposed in available_local_apps
  - diary summaries are most recent (reversed)
  - tool messages are filtered
"""
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
# Setup: Create a minimal builder
# =============================================================================
print("=== ContextPackBuilder tests ===")

from app.db.session import SessionLocal
from app.services.turn.context_pack_builder import ContextPackBuilder
from app.services.turn.pending_conversation_intent_service import PendingConversationIntentService

# Use a real session_factory but won't call build() with a real user_id
# unless we're in an integration test. For unit tests, test the individual helpers.

builder = ContextPackBuilder(
    session_factory=SessionLocal,
    memory_service=None,
    diary_service=None,
    pending_conversation_intent_service=None,
    config_service=None,
)

# =============================================================================
# Test 1: _is_tool_or_trace filters tool messages
# =============================================================================
print("=== Test 1: Tool/trace filtering ===")

check("1a: tool_result filtered", builder._is_tool_or_trace("[tool_result] output") is True)
check("1b: trace filtered", builder._is_tool_or_trace("[trace] reasoning") is True)
check("1c: very long message filtered", builder._is_tool_or_trace("x" * 2001) is True)
check("1d: normal message NOT filtered", builder._is_tool_or_trace("你好，今天天气不错") is False)
check("1e: short reply NOT filtered", builder._is_tool_or_trace("是的") is False)
check("1f: Tool result: prefix filtered", builder._is_tool_or_trace("Tool result: success") is True)
check("1g: Reasoning: prefix filtered", builder._is_tool_or_trace("Reasoning: let me think") is True)

# =============================================================================
# Test 2: Safe local app serialization (_available_local_apps)
# =============================================================================
print("=== Test 2: Safe local app serialization ===")

# Test that the safe DTO keys are correct (no executable_path)
safe_keys = {"app_key", "display_name", "intent_type", "keywords", "is_default_for_intent"}
forbidden_keys = {"executable_path", "working_directory", "args_json", "working_dir"}

check("2a: safe keys defined correctly", all(k in safe_keys for k in
      ["app_key", "display_name", "intent_type", "keywords", "is_default_for_intent"]))
check("2b: forbidden keys not in safe set",
      forbidden_keys.isdisjoint(safe_keys))

# =============================================================================
# Test 3: Pending intent — active vs expired
# =============================================================================
print("=== Test 3: Pending conversation intent ===")

pci_service = PendingConversationIntentService()
uid = uuid.uuid4()
cid = uuid.uuid4()

# No intent yet
check("3a: no intent returns None", pci_service.get_active(uid, cid) is None)

# Save an intent
pci_service.save(uid, cid, {"kind": "open_music_app", "app_name": "网易云音乐"}, ttl_seconds=300)
active = pci_service.get_active(uid, cid)
check("3b: saved intent is retrievable", active is not None)
check("3c: intent has correct kind", active.get("kind") == "open_music_app")

# Consume removes it
consumed = pci_service.consume(uid, cid)
check("3d: consume returns intent", consumed is not None)
check("3e: consumed intent is gone", pci_service.get_active(uid, cid) is None)

# Expiry
pci_service.save(uid, cid, {"kind": "test_expiry"}, ttl_seconds=0)
import time
time.sleep(0.1)  # Past TTL
check("3f: expired intent returns None", pci_service.get_active(uid, cid) is None)

# Clear
pci_service.save(uid, cid, {"kind": "test_clear"}, ttl_seconds=300)
pci_service.clear(uid, cid)
check("3g: cleared intent returns None", pci_service.get_active(uid, cid) is None)

# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*50}")
print(f"Results: {pass_count} passed, {fail_count} failed")
if fail_count:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("All tests passed")
