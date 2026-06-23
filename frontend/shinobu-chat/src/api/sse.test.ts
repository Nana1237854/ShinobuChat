import { normalizeStreamEvent, parseRawSseEvent, normalizePendingAction } from './sse';

describe('SSE parser', () => {
  it('parses named event payloads', () => {
    const raw = parseRawSseEvent('event: chunk\ndata: {"delta":"hello"}');
    expect(raw).toEqual({ eventName: 'chunk', payload: { delta: 'hello' } });
  });

  it('normalizes known stream events', () => {
    const event = normalizeStreamEvent({ eventName: 'done', payload: { conversation_id: 'c1', assistant_messages: [{ id: 'm1' }] } });
    expect(event?.type).toBe('done');
    expect(event).toEqual({ type: 'done', assistantMessages: [{ id: 'm1' }] });
  });

  it('normalizes conversation route mode', () => {
    const event = normalizeStreamEvent({
      eventName: 'conversation',
      payload: { conversation_id: 'c1', title: 'hello', route_mode: 'agent', user_message: { id: 'm1' } },
    });

    expect(event).toEqual({
      type: 'conversation',
      conversationId: 'c1',
      title: 'hello',
      routeMode: 'agent',
      userMessage: { id: 'm1' },
    });
  });

  it('normalizes pipeline stream events', () => {
    expect(normalizeStreamEvent({ eventName: 'emotion', payload: { emotion: 'thinking' } })).toEqual({
      type: 'emotion',
      emotion: 'thinking',
    });
    expect(normalizeStreamEvent({ eventName: 'audio', payload: { text: '你好。', audio: 'abc', emotion: 'happy' } })).toEqual({
      type: 'audio',
      text: '你好。',
      audio: 'abc',
      emotion: 'happy',
    });
    expect(normalizeStreamEvent({ eventName: 'progress', payload: { skill_name: 'search', message: 'Working', percent: 0.5 } })).toEqual({
      type: 'progress',
      skillName: 'search',
      message: 'Working',
      percent: 0.5,
    });
    expect(normalizeStreamEvent({ eventName: 'error', payload: { code: 'TIMEOUT', hint: 'Try again' } })).toEqual({
      type: 'error',
      code: 'TIMEOUT',
      hint: 'Try again',
    });
  });

  it('ignores unknown stream events', () => {
    expect(normalizeStreamEvent({ eventName: 'ping', payload: {} })).toBeNull();
  });

  describe('normalizePendingAction', () => {
    it('copies pending_action_id to id when id is missing', () => {
      const result = normalizePendingAction({
        pending_action_id: 'abc123',
        display_name: 'Music',
        app_key: 'music',
        status: 'waiting_confirmation',
      });
      expect(result.id).toBe('abc123');
      expect(result.pending_action_id).toBe('abc123');
      expect(result.display_name).toBe('Music');
    });

    it('keeps existing id when present', () => {
      const result = normalizePendingAction({
        id: 'existing-id',
        pending_action_id: 'different-id',
        display_name: 'Browser',
      });
      expect(result.id).toBe('existing-id');
    });

    it('falls back to app_key for description when display_name is missing', () => {
      const result = normalizePendingAction({
        pending_action_id: 'abc',
        app_key: 'myapp',
      });
      expect(result.description).toContain('myapp');
      expect(result.description).toContain('请求你的确认');
    });

    it('uses existing description when provided', () => {
      const result = normalizePendingAction({
        pending_action_id: 'abc',
        description: '请确认启动脚本',
      });
      expect(result.description).toBe('请确认启动脚本');
    });

    it('returns null/undefined as-is for falsy payload', () => {
      expect(normalizePendingAction(null)).toBeNull();
      expect(normalizePendingAction(undefined)).toBeUndefined();
    });
  });

  describe('stream events with normalized pending actions', () => {
    it('normalizes pending_action event with legacy payload', () => {
      const event = normalizeStreamEvent({
        eventName: 'pending_action',
        payload: {
          pending_action_id: 'abc',
          display_name: 'Music',
          status: 'waiting_confirmation',
        },
      });
      expect(event?.type).toBe('pending_action');
      expect((event as any).pendingAction.id).toBe('abc');
      expect((event as any).pendingAction.display_name).toBe('Music');
    });

    it('normalizes done event with legacy pending_action payload', () => {
      const event = normalizeStreamEvent({
        eventName: 'done',
        payload: {
          conversation_id: 'c1',
          assistant_messages: [{ id: 'm1', conversation_id: 'c1', role: 'assistant', content: 'hi', route_mode: 'chat', created_at: '2025-01-01T00:00:00' }],
          pending_action: {
            pending_action_id: 'pending-1',
            display_name: 'App',
            status: 'waiting_confirmation',
          },
        },
      });
      expect(event?.type).toBe('done');
      expect((event as any).pendingAction.id).toBe('pending-1');
    });
  });
});
