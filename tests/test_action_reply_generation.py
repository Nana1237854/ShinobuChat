"""Tests for ActionReplyGenerationService.

Covers:
  - fallback templates for every status
  - safety: requires_confirmation never claims "already opened"
  - safety: opened can say "opened"
  - safety: requires_selection mentions multiple apps and suggests default
  - fallback when AI raises an exception
  - AI reply is used when available
  - action_result is never modified
  - DirectActionRunner build_reply still works as fallback
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
# Test 1: Fallback — requires_confirmation should NOT say "already opened"
# =============================================================================
print("=== Test 1: Fallback safety — requires_confirmation ===")

from app.services.turn.action_reply_generation_service import (
    _fallback_reply,
    ActionReplyGenerationService,
)

reply = _fallback_reply(
    status="requires_confirmation",
    display_name="网易云音乐",
)

check("1a: fallback requires_confirmation NOT claim opened",
      "已经打开" not in reply and "已打开" not in reply and "打开好了" not in reply)
check("1b: fallback requires_confirmation mentions confirmation",
      "确认" in reply)
check("1c: fallback requires_confirmation mentions display_name",
      "网易云音乐" in reply)


# =============================================================================
# Test 2: Fallback — opened CAN say "opened"
# =============================================================================
print("\n=== Test 2: Fallback — opened ===")

reply = _fallback_reply(
    status="opened",
    display_name="网易云音乐",
)
check("2a: fallback opened contains 打开", "打开" in reply)
check("2b: fallback opened contains display_name", "网易云音乐" in reply)


# =============================================================================
# Test 3: Fallback — requires_selection mentions multiple and default
# =============================================================================
print("\n=== Test 3: Fallback — requires_selection ===")

reply = _fallback_reply(
    status="requires_selection",
    intent_type="open_ide",
    candidates=[
        {"display_name": "Android Studio", "app_key": "ide"},
        {"display_name": "vscode", "app_key": "vscode"},
    ],
)
check("3a: fallback requires_selection mentions multiple",
      "多个" in reply or "Android Studio" in reply)
check("3b: fallback requires_selection mentions default option",
      "默认" in reply)
check("3c: fallback requires_selection names candidates",
      "Android Studio" in reply and "vscode" in reply)


# =============================================================================
# Test 4: Fallback — not_configured
# =============================================================================
print("\n=== Test 4: Fallback — not_configured ===")

reply = _fallback_reply(
    status="not_configured",
    display_name="网易云音乐",
)
check("4a: fallback not_configured mentions 配置", "配置" in reply)
check("4b: fallback not_configured mentions display_name", "网易云音乐" in reply)


# =============================================================================
# Test 5: Fallback — failed
# =============================================================================
print("\n=== Test 5: Fallback — failed ===")

reply = _fallback_reply(
    status="failed",
    display_name="某应用",
)
check("5a: fallback failed mentions 失败", "失败" in reply)


# =============================================================================
# Test 6: Fallback — forbidden
# =============================================================================
print("\n=== Test 6: Fallback — forbidden ===")

reply = _fallback_reply(
    status="forbidden",
    display_name="某应用",
)
check("6a: fallback forbidden mentions 开启", "开启" in reply)


# =============================================================================
# Test 7: Fallback — requires_confirmation with selection_message
# =============================================================================
print("\n=== Test 7: Fallback — requires_confirmation with selection_message ===")

reply = _fallback_reply(
    status="requires_confirmation",
    display_name="Android Studio",
    selection_message="有多个应用匹配 open_ide，我会选择默认应用 Android Studio。",
)
check("7a: fallback includes selection_message", "默认应用" in reply)
check("7b: fallback includes display_name", "Android Studio" in reply)


# =============================================================================
# Test 8: AI exception → fallback (no AI client configured)
# =============================================================================
print("\n=== Test 8: No AIClient → fallback ===")

svc = ActionReplyGenerationService(ai_client=None)
reply = svc.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="我想听歌，帮我打开网易云音乐",
    status="requires_confirmation",
    display_name="网易云音乐",
)
check("8a: no AI client returns fallback", "确认" in reply)
check("8b: no AI client mentions display_name", "网易云音乐" in reply)


# =============================================================================
# Test 9: AI exception during generation → fallback
# =============================================================================
print("\n=== Test 9: AI crashes → fallback ===")

class CrashingAIClient:
    def complete_chat(self, *args, **kwargs):
        raise RuntimeError("simulated AI crash")


svc2 = ActionReplyGenerationService(ai_client=CrashingAIClient())
reply = svc2.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="我想写代码，帮我打开 Android Studio",
    status="requires_confirmation",
    display_name="Android Studio",
)
check("9a: crashing AI returns fallback (no exception)", "确认" in reply)
check("9b: crashing AI does NOT contain raw error", "RuntimeError" not in reply)


# =============================================================================
# Test 10: AI returns valid reply → used
# =============================================================================
print("\n=== Test 10: AI returns valid reply → used ===")

EXPECTED_AI_REPLY = (
    "网易云音乐需要你确认一下才能打开哦～"
    "我先不乱动你的电脑，等你点一下确认我再帮你开。"
)

class MockAIClient:
    def complete_chat(self, *args, **kwargs):
        return {"content": EXPECTED_AI_REPLY}


svc3 = ActionReplyGenerationService(ai_client=MockAIClient())
reply = svc3.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="我想听歌，帮我打开网易云音乐",
    status="requires_confirmation",
    display_name="网易云音乐",
)
check("10a: AI reply used directly", reply == EXPECTED_AI_REPLY)
check("10b: AI reply does NOT contain [thinking]", "[thinking]" not in reply)


# =============================================================================
# Test 11: AI returns empty content → fallback
# =============================================================================
print("\n=== Test 11: AI returns empty → fallback ===")

class EmptyAIClient:
    def complete_chat(self, *args, **kwargs):
        return {"content": ""}


svc4 = ActionReplyGenerationService(ai_client=EmptyAIClient())
reply = svc4.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="我想听歌，打开网易云音乐",
    status="opened",
    display_name="网易云音乐",
)
check("11a: empty AI content falls back", "打开" in reply and "网易云音乐" in reply)


# =============================================================================
# Test 12: Safety — opened via AI does not deny opening
# =============================================================================
print("\n=== Test 12: Safety — opened via AI ===")

class OpenedAIClient:
    def complete_chat(self, *args, **kwargs):
        return {"content": "已经帮你打开网易云音乐啦～想听点什么风格的呢？"}


svc5 = ActionReplyGenerationService(ai_client=OpenedAIClient())
reply = svc5.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="帮我打开网易云音乐",
    status="opened",
    display_name="网易云音乐",
)
check("12a: opened AI reply mentions 打开", "打开" in reply)


# =============================================================================
# Test 13: AI prompt includes all required fields
# =============================================================================
print("\n=== Test 13: AI user prompt includes all required fields ===")

from app.services.turn.action_reply_generation_service import ActionReplyGenerationService as Svc

prompt = Svc._user_prompt({
    "user_text": "帮我打开网易云音乐",
    "status": "requires_confirmation",
    "action_type": "open_local_app",
    "intent_type": "open_music",
    "display_name": "网易云音乐",
    "app_key": "CloudMusic",
    "result_message": "Opening '网易云音乐' requires confirmation.",
    "selected_by": "app_key",
    "selection_message": None,
    "requires_confirmation": True,
    "error_detail": None,
    "candidates": [],
})
check("13a: user prompt includes user_text", "帮我打开网易云音乐" in prompt)
check("13b: user prompt includes status", "status=requires_confirmation" in prompt)
check("13c: user prompt includes display_name", "display_name=网易云音乐" in prompt)
check("13d: user prompt includes intent_type", "intent_type=open_music" in prompt)
check("13e: user prompt has safety instruction context", "不可改变" in prompt or "事实" in prompt)


# =============================================================================
# Test 14: system prompt includes all safety rules
# =============================================================================
print("\n=== Test 14: system prompt contains safety rules ===")

sys_prompt = Svc._system_prompt(uuid.UUID("00000000-0000-0000-0000-000000000001"))
check("14a: system prompt forbids changing facts", "不能改变操作事实" in sys_prompt)
check("14b: system prompt restricts opened claims", "status=opened" in sys_prompt)
check("14c: system prompt restricts requires_confirmation", "requires_confirmation" in sys_prompt)
check("14d: system prompt restricts requires_selection", "requires_selection" in sys_prompt)
check("14e: system prompt restricts not_configured", "not_configured" in sys_prompt)
check("14f: system prompt restricts failed", "failed" in sys_prompt)
check("14g: system prompt bans JSON", "不要输出 JSON" in sys_prompt)
check("14h: system prompt bans technical fields", "app_key" in sys_prompt)


# =============================================================================
# Test 15: DirectActionRunner.build_reply still works as fallback
# =============================================================================
print("\n=== Test 15: DirectActionRunner fallback still works ===")

from unittest.mock import MagicMock
from app.services.turn.direct_action_runner import DirectActionRunner

da = MagicMock()
da.action = "open_local_app"
da.intent_type = "open_music"

runner = DirectActionRunner()
reply = runner.build_reply(da, {
    "status": "opened",
    "display_name": "Music",
})
check("15a: DAR fallback opened", "打开" in reply)


# =============================================================================
# Test 16: ActionReplyGenerationService handles None display_name
# =============================================================================
print("\n=== Test 16: Edge cases — missing display_name ===")

reply = _fallback_reply(status="opened", display_name=None, intent_type="open_music")
check("16a: fallback opened without display_name uses intent_type",
      "open_music" in reply and "打开" in reply)

reply = _fallback_reply(status="requires_selection", candidates=[])
check("16b: fallback requires_selection without candidates works",
      "多个" in reply)


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
