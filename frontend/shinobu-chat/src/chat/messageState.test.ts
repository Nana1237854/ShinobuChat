import { completeAssistantMessage, mergeServerMessages } from './messageState';
import type { ChatMessage } from '../types';

function message(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: 'm1',
    conversation_id: 'c1',
    role: 'user',
    content: 'hello',
    created_at: '2026-05-13T00:00:00.000Z',
    status: 'sent',
    ...overrides,
  };
}

describe('message state helpers', () => {
  it('replaces the streaming assistant bubble with the saved assistant message', () => {
    const current = [
      message({ id: 'u1', role: 'user', content: '今天我要学习python！' }),
      message({
        id: 'pending-1',
        role: 'assistant',
        content: '听起来是个很棒的规划！',
        status: 'streaming',
        local: true,
      }),
    ];
    const saved = message({
      id: 'a1',
      role: 'assistant',
      content: '听起来是个很棒的规划！',
      status: 'sent',
    });

    expect(completeAssistantMessage(current, 'pending-1', saved)).toEqual([
      current[0],
      saved,
    ]);
  });

  it('keeps an in-flight local message when server history refreshes mid-stream', () => {
    const localAssistant = message({
      id: 'pending-1',
      role: 'assistant',
      content: 'partial',
      status: 'streaming',
      local: true,
    });
    const serverMessages = [
      message({ id: 'u1', role: 'user', content: 'hello' }),
    ];

    expect(mergeServerMessages([localAssistant], serverMessages, true)).toEqual([
      serverMessages[0],
      localAssistant,
    ]);
  });
});
