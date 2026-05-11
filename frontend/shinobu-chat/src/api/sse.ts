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
    return { type: 'conversation', payload: raw.payload as Extract<StreamEvent, { type: 'conversation' }>['payload'] };
  }
  if (raw.eventName === 'chunk') {
    return { type: 'chunk', payload: raw.payload as Extract<StreamEvent, { type: 'chunk' }>['payload'] };
  }
  if (raw.eventName === 'done') {
    return { type: 'done', payload: raw.payload as Extract<StreamEvent, { type: 'done' }>['payload'] };
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
