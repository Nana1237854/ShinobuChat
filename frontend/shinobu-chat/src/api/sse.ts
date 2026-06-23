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
    const payload = raw.payload as {
      conversation_id: string;
      title: string;
      route_mode: Extract<StreamEvent, { type: 'conversation' }>['routeMode'];
      user_message: Extract<StreamEvent, { type: 'conversation' }>['userMessage'];
    };
    return {
      type: 'conversation',
      conversationId: payload.conversation_id,
      title: payload.title,
      routeMode: payload.route_mode,
      userMessage: payload.user_message,
    };
  }
  if (raw.eventName === 'chunk') {
    const payload = raw.payload as { delta: string };
    return { type: 'chunk', delta: payload.delta };
  }
  if (raw.eventName === 'emotion') {
    const payload = raw.payload as {
      emotion?: string;
      emotion_label?: string;
      confidence?: number | null;
      intensity?: number | null;
      reply_style_hint?: string | null;
    };
    const emotion = payload.emotion ?? payload.emotion_label ?? 'neutral';
    const hasEmotionState = typeof payload.emotion_label === 'string';
    return {
      type: 'emotion',
      emotion,
      ...(hasEmotionState
        ? {
            emotionState: {
              emotion_label: payload.emotion_label ?? emotion,
              confidence: payload.confidence ?? null,
              intensity: payload.intensity ?? null,
              reply_style_hint: payload.reply_style_hint ?? null,
            },
          }
        : {}),
    };
  }
  if (raw.eventName === 'audio') {
    const payload = raw.payload as {
      text: string;
      audio: string;
      emotion: string | null;
      emotion_state?: {
        emotion_label?: string;
        confidence?: number | null;
        intensity?: number | null;
        reply_style_hint?: string | null;
      } | null;
    };
    return {
      type: 'audio',
      text: payload.text,
      audio: payload.audio,
      emotion: payload.emotion,
      ...(payload.emotion_state
        ? {
            emotionState: {
              emotion_label: payload.emotion_state.emotion_label ?? payload.emotion ?? 'neutral',
              confidence: payload.emotion_state.confidence ?? null,
              intensity: payload.emotion_state.intensity ?? null,
              reply_style_hint: payload.emotion_state.reply_style_hint ?? null,
            },
          }
        : {}),
    };
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
    const payload = raw.payload as {
      assistant_messages?: Extract<StreamEvent, { type: 'done' }>['assistantMessages'];
      emotion_state?: {
        emotion_label?: string;
        confidence?: number | null;
        intensity?: number | null;
        reply_style_hint?: string | null;
      } | null;
      pending_action?: Extract<StreamEvent, { type: 'done' }>['pendingAction'];
      assistant_message?: never;
    };
    return {
      type: 'done',
      assistantMessages: payload.assistant_messages ?? [],
      ...(payload.emotion_state
        ? {
            emotionState: {
              emotion_label: payload.emotion_state.emotion_label ?? 'neutral',
              confidence: payload.emotion_state.confidence ?? null,
              intensity: payload.emotion_state.intensity ?? null,
              reply_style_hint: payload.emotion_state.reply_style_hint ?? null,
            },
          }
        : {}),
      ...(payload.pending_action
        ? { pendingAction: payload.pending_action }
        : {}),
    };
  }
  if (raw.eventName === 'pending_action') {
    const payload = raw.payload as Extract<StreamEvent, { type: 'pending_action' }>['pendingAction'];
    return { type: 'pending_action', pendingAction: payload };
  }
  if (raw.eventName === 'action') {
    const payload = raw.payload as Extract<StreamEvent, { type: 'action' }>['action'];
    return { type: 'action', action: payload };
  }
  // Unknown event types are silently ignored (no error)
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
