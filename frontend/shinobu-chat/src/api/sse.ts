import type { StreamEvent } from '../types';

type RawSseEvent = {
  eventName: string;
  payload: unknown;
};

export function parseRawSseEvent(rawEvent: string): RawSseEvent | null {
  const lines = rawEvent.split(/\r?\n/);
  let eventName = 'message';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return null;
  return {
    eventName,
    payload: JSON.parse(dataLines.join('\n')),
  };
}

export function normalizeStreamEvent(raw: RawSseEvent): StreamEvent | null {
  if (raw.eventName === 'conversation') {
    const payload = raw.payload as { conversation_id: string; title: string; user_message: Extract<StreamEvent, { type: 'conversation' }>['userMessage'] };
    return {
      type: 'conversation',
      conversationId: payload.conversation_id,
      title: payload.title,
      userMessage: payload.user_message,
    };
  }
  if (raw.eventName === 'chunk') {
    const payload = raw.payload as { delta: string };
    return { type: 'chunk', delta: payload.delta };
  }
  if (raw.eventName === 'emotion') {
    const payload = raw.payload as { emotion: string };
    return { type: 'emotion', emotion: payload.emotion };
  }
  if (raw.eventName === 'progress') {
    const payload = raw.payload as { skill_name: string; message: string; percent: number };
    return { type: 'progress', skillName: payload.skill_name, message: payload.message, percent: payload.percent };
  }
  if (raw.eventName === 'error') {
    const payload = raw.payload as { code: string; hint: string };
    return { type: 'error', code: payload.code, hint: payload.hint };
  }
  if (raw.eventName === 'done') {
    const payload = raw.payload as { assistant_message: Extract<StreamEvent, { type: 'done' }>['assistantMessage'] };
    return { type: 'done', assistantMessage: payload.assistant_message };
  }
  return null;
}

export async function consumeSseStream(
  response: Response,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error('Response body is not readable');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.search(/\r?\n\r?\n/);

    while (boundary !== -1) {
      const separator = buffer.match(/\r?\n\r?\n/)?.[0] ?? '\n\n';
      const raw = buffer.slice(0, boundary).trim();
      buffer = buffer.slice(boundary + separator.length);
      if (raw) {
        const parsed = parseRawSseEvent(raw);
        const event = parsed ? normalizeStreamEvent(parsed) : null;
        if (event) onEvent(event);
      }
      boundary = buffer.search(/\r?\n\r?\n/);
    }
  }
}
