import { normalizeStreamEvent, parseRawSseEvent } from './sse';

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
});
