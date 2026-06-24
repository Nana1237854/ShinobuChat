"""Tests for ContextIntentResolver.

Covers:
  - JSON parsing with various LLM output formats
  - Validation of action, confidence, intent_type
  - Low confidence → chat demotion
  - Hallucinated app_key is NOT executed (validated higher up by MessageService)
  - Invalid JSON falls back to chat
"""
import sys

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
print("=== ContextIntentResolver tests ===")

from app.schemas.context_intent import ContextIntentResult, ContextPack
from app.services.turn.context_intent_resolver import ContextIntentResolver

# =============================================================================
# Test 1: Parse clean JSON
# =============================================================================
print("=== Test 1: JSON parsing ===")

clean_json = '{"action": "open_local_app", "intent_type": "open_music", "app_name": "网易云音乐", "confidence": 0.93, "reason": "test"}'
parsed = ContextIntentResolver._parse_json(clean_json)
check("1a: clean JSON parsed", parsed["action"] == "open_local_app")
check("1b: clean JSON confidence", parsed["confidence"] == 0.93)

# =============================================================================
# Test 2: Parse JSON with markdown fences
# =============================================================================
print("=== Test 2: Markdown fence handling ===")

markdown_json = '```json\n{"action": "chat", "confidence": 0.9}\n```'
parsed = ContextIntentResolver._parse_json(markdown_json)
check("2a: markdown json fence stripped", parsed["action"] == "chat")

no_lang_json = '```\n{"action": "clarify", "clarification_question": "test?"}\n```'
parsed = ContextIntentResolver._parse_json(no_lang_json)
check("2b: markdown fence without lang stripped", parsed["action"] == "clarify")

# =============================================================================
# Test 3: Parse JSON with surrounding text
# =============================================================================
print("=== Test 3: JSON extraction from text ===")

text_with_json = 'Here is my analysis:\n{"action": "chat", "confidence": 0.85}\nThat is all.'
parsed = ContextIntentResolver._parse_json(text_with_json)
check("3a: JSON extracted from text", parsed["action"] == "chat")

# =============================================================================
# Test 4: Invalid JSON fallback
# =============================================================================
print("=== Test 4: Invalid JSON handling ===")

try:
    ContextIntentResolver._parse_json("not json at all")
    check("4a: invalid JSON raises ValueError", False)
except ValueError:
    check("4a: invalid JSON raises ValueError", True)

# =============================================================================
# Test 5: Validate action whitelist
# =============================================================================
print("=== Test 5: Action validation ===")

result = ContextIntentResolver._validate({"action": "open_local_app", "confidence": 0.9})
check("5a: open_local_app valid", result.action == "open_local_app")

result = ContextIntentResolver._validate({"action": "chat", "confidence": 0.9})
check("5b: chat valid", result.action == "chat")

result = ContextIntentResolver._validate({"action": "invalid_action", "confidence": 0.9})
check("5c: invalid action → chat", result.action == "chat")

result = ContextIntentResolver._validate({"action": "none", "confidence": 0.9})
check("5d: none valid", result.action == "none")

# =============================================================================
# Test 6: Confidence thresholds
# =============================================================================
print("=== Test 6: Confidence validation ===")

result = ContextIntentResolver._validate({"action": "open_local_app", "confidence": 0.93})
check("6a: high confidence open_local_app kept", result.action == "open_local_app")

result = ContextIntentResolver._validate({"action": "open_local_app", "confidence": 0.5})
check("6b: low confidence open_local_app → chat", result.action == "chat")

result = ContextIntentResolver._validate({"action": "open_local_app", "confidence": "not_a_number"})
check("6c: non-numeric confidence → 0 → chat", result.action == "chat")

result = ContextIntentResolver._validate({"action": "open_local_app", "confidence": 1.5})
check("6d: clamped to 1.0, still open_local_app", result.action == "open_local_app" and result.confidence == 1.0)

# =============================================================================
# Test 7: Invalid intent_type
# =============================================================================
print("=== Test 7: Intent type validation ===")

result = ContextIntentResolver._validate({
    "action": "open_local_app",
    "intent_type": "open_music",
    "confidence": 0.95,
})
check("7a: open_music valid", result.intent_type == "open_music")

result = ContextIntentResolver._validate({
    "action": "open_local_app",
    "intent_type": "evil_action",
    "confidence": 0.95,
})
check("7b: invalid intent_type → None", result.intent_type is None)

# =============================================================================
# Test 8: Pydantic model validation
# =============================================================================
print("=== Test 8: Pydantic model validation ===")

try:
    ContextIntentResult(action="open_local_app", confidence=0.9)
    check("8a: valid Pydantic model created", True)
except Exception:
    check("8a: valid Pydantic model created", False)

try:
    ContextIntentResult(action="open_local_app", confidence=-0.5)
    check("8b: negative confidence rejected by Pydantic", False)
except Exception:
    check("8b: negative confidence rejected by Pydantic", True)

# =============================================================================
# Test 9: User prompt builder
# =============================================================================
print("=== Test 9: User prompt builder ===")

pack = ContextPack(
    recent_messages=[
        {"role": "user", "content": "我想听歌"},
        {"role": "assistant", "content": "要不要在网易云上听？"},
    ],
    pending_conversation_intent={"kind": "open_music_app", "app_name": "网易云音乐"},
    available_local_apps=[{
        "app_key": "cloudmusic",
        "display_name": "网易云音乐",
        "intent_type": "open_music",
        "keywords": ["网易云", "音乐"],
        "is_default_for_intent": True,
    }],
    conversation_mode="companion",
)

prompt = ContextIntentResolver._build_user_prompt("是的", pack)
check("9a: prompt contains user text", "是的" in prompt)
check("9b: prompt contains recent message", "我想听歌" in prompt)
check("9c: prompt contains pending intent", "open_music_app" in prompt)
check("9d: prompt contains local app", "cloudmusic" in prompt)
check("9e: prompt does NOT contain executable_path", "executable_path" not in prompt)
check("9f: prompt does NOT contain working_directory", "working_directory" not in prompt)

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
