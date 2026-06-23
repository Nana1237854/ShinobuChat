"""Tests for AI upstream error handling (402, 401, 429, 5xx, timeout).

Covers:
  - _friendly_ai_error_hint returns correct messages
  - create_streaming_response() catches UpstreamServiceError and yields error SSE
  - create_streaming_response() does not raise on UpstreamServiceError
  - SSE error event has correct code and hint
  - ActionReplyGenerationService falls back to template on UpstreamServiceError
  - Direct Action requires_confirmation still emits pending_action when LLM fails
"""
import asyncio
import sys
import uuid
from unittest.mock import MagicMock, patch

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
# Test 1: _friendly_ai_error_hint — all error types
# =============================================================================
print("=== Test 1: _friendly_ai_error_hint ===")

from app.services.message_service import _friendly_ai_error_hint

hint = _friendly_ai_error_hint('{"error":{"message":"Insufficient Balance","type":"unknown_error"}}')
check("1a: insufficient balance → 余额不足", "余额不足" in hint)
check("1b: insufficient balance → mentions API Key", "API Key" in hint or "apikey" in hint.lower())

hint = _friendly_ai_error_hint("HTTP Error 402: Payment Required")
check("1c: 402 Payment Required → 余额不足", "余额不足" in hint)

hint = _friendly_ai_error_hint("HTTP Error 401: Unauthorized")
check("1d: 401 → API Key 无效", "API Key" in hint and "无效" in hint)

hint = _friendly_ai_error_hint("Invalid API Key")
check("1e: invalid api key → API Key 无效", "无效" in hint)

hint = _friendly_ai_error_hint("HTTP Error 429: Rate Limit Exceeded")
check("1f: 429 → 频繁", "频繁" in hint)

hint = _friendly_ai_error_hint("rate limit exceeded")
check("1g: rate limit → 频繁", "频繁" in hint)

hint = _friendly_ai_error_hint("Some unknown error")
check("1h: unknown → generic message", "暂时不可用" in hint)


# =============================================================================
# Test 2: ActionReplyGenerationService falls back on UpstreamServiceError
# =============================================================================
print("\n=== Test 2: ActionReply falls back on UpstreamServiceError ===")

from app.core.exceptions import UpstreamServiceError
from app.services.turn.action_reply_generation_service import ActionReplyGenerationService


class UpstreamCrashingAIClient:
    def complete_chat(self, *args, **kwargs):
        raise UpstreamServiceError(
            'AI API request failed: {"error":{"message":"Insufficient Balance","type":"unknown_error"}}'
        )


svc = ActionReplyGenerationService(ai_client=UpstreamCrashingAIClient())
reply = svc.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="我想听歌，帮我打开网易云音乐",
    status="requires_confirmation",
    display_name="网易云音乐",
)
check("2a: UpstreamServiceError → fallback (no raise)", "确认" in reply)
check("2b: fallback contains display_name", "网易云音乐" in reply)
check("2c: fallback does NOT contain raw error", "Insufficient" not in reply)


# =============================================================================
# Test 3: ActionReplyGenerationService falls back on opened status too
# =============================================================================
print("\n=== Test 3: ActionReply fallback — opened with UpstreamServiceError ===")

reply = svc.generate(
    user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    user_text="帮我打开网易云音乐",
    status="opened",
    display_name="网易云音乐",
)
check("3a: opened fallback contains 打开", "打开" in reply)
check("3b: opened fallback contains display_name", "网易云音乐" in reply)


# =============================================================================
# Test 4: Direct Action pending_action emitted before LLM call
# =============================================================================
print("\n=== Test 4: Direct Action pending_action order invariant ===")

# Verify that _handle_direct_action yields pending_action BEFORE calling LLM
# by inspecting the code structure (design-level test)
from app.services.message_service import MessageService
import inspect

source = inspect.getsource(MessageService._handle_direct_action)
# The pending_action yield should appear before action_reply_generation_service.generate call
pending_pos = source.find("pending_action")
llm_pos = source.find("action_reply_generation_service.generate")
check("4a: pending_action yield before LLM generate call in source",
      pending_pos > 0 and llm_pos > 0 and pending_pos < llm_pos)


# =============================================================================
# Test 5: SSE error event format is correct
# =============================================================================
print("\n=== Test 5: SSE error event format ===")

from app.services.stream_events import SseEncoder, StreamEvent
from app.services.turn.stream_event_service import StreamEventService

sse = SseEncoder()
event_service = StreamEventService(sse)

error_event = event_service.error(
    code="ai_upstream_error",
    hint="当前 AI 服务余额不足，暂时无法生成回复。请检查模型服务余额或更换可用 API Key。",
)
formatted = event_service.format(error_event)

check("5a: SSE format contains event: error", "event: error" in formatted)
check("5b: SSE format contains ai_upstream_error code", "ai_upstream_error" in formatted)
check("5c: SSE format contains 余额不足", "余额不足" in formatted)
check("5d: SSE format is valid (ends with double newline)", formatted.endswith("\n\n"))


# =============================================================================
# Test 6: create_streaming_response catches UpstreamServiceError
# =============================================================================
print("\n=== Test 6: create_streaming_response catches UpstreamServiceError ===")


async def run_stream_error_test():
    from app.services.stream_events import SseEncoder
    from app.services.turn.stream_event_service import StreamEventService
    from app.services.turn.reply_generation_service import ReplyGenerationService
    from app.services.turn.memory_write_scheduler import MemoryWriteScheduler
    from app.services.turn.voice_reply_service import VoiceReplyService

    # ── Mock AIClient that raises on stream_chat ──
    mock_ai = MagicMock()
    mock_ai.stream_chat.side_effect = UpstreamServiceError(
        'AI API request failed: {"error":{"message":"Insufficient Balance"}}'
    )

    # ── Mock ConversationTurnService ──
    mock_turn = MagicMock()

    import datetime as dt

    class FakeMessage:
        id = uuid.UUID("00000000-0000-0000-0000-000000000010")
        conversation_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
        role = "user"
        content = "你好"
        route_mode = "chat"
        created_at = dt.datetime(2025, 1, 1, 0, 0, 0)

    class FakeConversation:
        id = uuid.UUID("00000000-0000-0000-0000-000000000020")
        title = "Test"

    class FakeState:
        conversation = FakeConversation()
        user_message = FakeMessage()
        route_mode = __import__("app.schemas.message", fromlist=["RouteMode"]).RouteMode.CHAT
        direct_action = None
        conversation_mode = "companion"

    fake_state = FakeState()
    fake_messages = [{"role": "system", "content": "..."}, {"role": "user", "content": "你好"}]

    mock_turn.prepare_turn.return_value = (fake_state, fake_messages)

    # ── Mock ConversationService ──
    mock_convs = MagicMock()
    mock_convs.list_messages.return_value = [FakeMessage()]

    # ── Real services that don't need DB ──
    real_sse = SseEncoder()
    event_svc = StreamEventService(real_sse)
    reply_gen = ReplyGenerationService(ai_client=mock_ai, agent_coordinator=None, skill_manager=None)
    voice_reply = VoiceReplyService(voice_service=None, sse=real_sse)
    mem_scheduler = MemoryWriteScheduler(memory_agent=None)

    # ── Construct MessageService with mocks ──
    svc = MessageService.__new__(MessageService)
    svc.db = MagicMock()
    svc.conversations = mock_convs
    svc.skill_registry = MagicMock()
    svc.agent = MagicMock()
    svc.agent_orchestrator = MagicMock()
    svc.ai_client = mock_ai
    svc.sse = real_sse
    svc.voice_service = None
    svc.agent_coordinator = None
    svc.memory_agent = None
    svc.config_service = None
    svc.skill_manager = None
    svc.turn_service = mock_turn
    svc.event_service = event_svc
    svc.reply_generation_service = reply_gen
    svc.direct_action_runner = MagicMock()
    svc.voice_reply_service = voice_reply
    svc.memory_write_scheduler = mem_scheduler
    svc.action_reply_generation_service = MagicMock()

    from app.schemas.message import MessageCreate

    payload = MessageCreate(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        content="你好",
        route_mode="chat",
    )

    events = []
    try:
        async for sse_chunk in svc.create_streaming_response(payload):
            events.append(sse_chunk)
    except Exception as e:
        return False, f"create_streaming_response raised: {e}", events

    return True, None, events


success, error_msg, events = asyncio.run(run_stream_error_test())
check("6a: create_streaming_response does not raise on UpstreamServiceError", success)

if error_msg:
    print(f"       Error: {error_msg}")

# Find the error event
error_events = [e for e in events if "event: error" in e]
check("6b: SSE output contains error event", len(error_events) >= 1)

if error_events:
    check("6c: error event has ai_upstream_error code", "ai_upstream_error" in error_events[0])
    check("6d: error event contains 余额不足 hint", "余额不足" in error_events[0])

# Verify conversation_started was still emitted
conv_events = [e for e in events if "event: conversation" in e]
check("6e: conversation_started emitted before error", len(conv_events) >= 1)


# =============================================================================
# Test 7: Empty AI response → error event (not crash)
# =============================================================================
print("\n=== Test 7: Empty AI response → error event ===")


async def run_empty_response_test():
    import datetime as dt
    from app.services.stream_events import SseEncoder
    from app.services.turn.stream_event_service import StreamEventService
    from app.services.turn.reply_generation_service import ReplyGenerationService
    from app.services.turn.memory_write_scheduler import MemoryWriteScheduler
    from app.services.turn.voice_reply_service import VoiceReplyService

    # ── Mock AIClient that returns empty stream ──
    mock_ai = MagicMock()
    mock_ai.stream_chat.return_value = iter([])  # empty iterator → no chunks

    mock_turn = MagicMock()

    class FakeMessage:
        id = uuid.UUID("00000000-0000-0000-0000-000000000010")
        conversation_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
        role = "user"
        content = "你好"
        route_mode = "chat"
        created_at = dt.datetime(2025, 1, 1, 0, 0, 0)

    class FakeConversation:
        id = uuid.UUID("00000000-0000-0000-0000-000000000020")
        title = "Test"

    class FakeState:
        conversation = FakeConversation()
        user_message = FakeMessage()
        route_mode = __import__("app.schemas.message", fromlist=["RouteMode"]).RouteMode.CHAT
        direct_action = None
        conversation_mode = "companion"

    fake_state = FakeState()
    fake_messages = [{"role": "system", "content": "..."}, {"role": "user", "content": "你好"}]

    mock_turn.prepare_turn.return_value = (fake_state, fake_messages)

    mock_convs = MagicMock()
    mock_convs.list_messages.return_value = [FakeMessage()]

    real_sse = SseEncoder()
    event_svc = StreamEventService(real_sse)
    reply_gen = ReplyGenerationService(ai_client=mock_ai, agent_coordinator=None, skill_manager=None)
    voice_reply = VoiceReplyService(voice_service=None, sse=real_sse)
    mem_scheduler = MemoryWriteScheduler(memory_agent=None)

    svc = MessageService.__new__(MessageService)
    svc.db = MagicMock()
    svc.conversations = mock_convs
    svc.skill_registry = MagicMock()
    svc.agent = MagicMock()
    svc.agent_orchestrator = MagicMock()
    svc.ai_client = mock_ai
    svc.sse = real_sse
    svc.voice_service = None
    svc.agent_coordinator = None
    svc.memory_agent = None
    svc.config_service = None
    svc.skill_manager = None
    svc.turn_service = mock_turn
    svc.event_service = event_svc
    svc.reply_generation_service = reply_gen
    svc.direct_action_runner = MagicMock()
    svc.voice_reply_service = voice_reply
    svc.memory_write_scheduler = mem_scheduler
    svc.action_reply_generation_service = MagicMock()

    from app.schemas.message import MessageCreate

    payload = MessageCreate(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        content="你好",
        route_mode="chat",
    )

    events = []
    try:
        async for sse_chunk in svc.create_streaming_response(payload):
            events.append(sse_chunk)
    except Exception as e:
        return False, f"create_streaming_response raised: {e}", events

    return True, None, events


success, error_msg, events = asyncio.run(run_empty_response_test())
check("7a: empty response does not crash SSE", success)

error_events = [e for e in events if "event: error" in e]
check("7b: empty response → error event emitted", len(error_events) >= 1)
if error_events:
    check("7c: empty response → ai_upstream_error code", "ai_upstream_error" in error_events[0])


# =============================================================================
# Test 8: StreamEventService.error() produces correct payload
# =============================================================================
print("\n=== Test 8: StreamEventService.error() payload ===")

from app.services.turn.stream_event_service import StreamEventService
from app.services.stream_events import SseEncoder

sse2 = SseEncoder()
svc2 = StreamEventService(sse2)

event = svc2.error(code="ai_upstream_error", hint="测试错误信息")
check("8a: error event name is 'error'", event.event == "error")
check("8b: error payload has code", event.payload.get("code") == "ai_upstream_error")
check("8c: error payload has hint", event.payload.get("hint") == "测试错误信息")


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
