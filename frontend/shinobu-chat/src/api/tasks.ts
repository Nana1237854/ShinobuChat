/** SSE-based task progress reader (F16). */

export type TaskEventType =
  | 'task_started'
  | 'task_progress'
  | 'task_waiting_confirmation'
  | 'task_completed'
  | 'task_failed'
  | 'task_cancelled';

export interface TaskEvent {
  event: TaskEventType;
  payload: Record<string, unknown>;
  timestamp: string;
}

export function streamTaskEvents(
  taskId: string,
  accessToken: string,
  onEvent: (event: TaskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    fetch(`/api/v1/tasks/${taskId}/events`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: 'text/event-stream',
      },
      signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          reject(new Error(`Task SSE failed: ${response.status}`));
          return;
        }
        const reader = response.body?.getReader();
        if (!reader) {
          reject(new Error('No response body'));
          return;
        }
        const decoder = new TextDecoder();
        let buffer = '';
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split('\n\n');
            buffer = parts.pop() || '';
            for (const part of parts) {
              const lines = part.split('\n');
              let eventName = '';
              let data = '';
              for (const line of lines) {
                if (line.startsWith('event: ')) {
                  eventName = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                  data = line.slice(6).trim();
                }
              }
              if (eventName && data) {
                try {
                  const payload = JSON.parse(data);
                  onEvent({ event: eventName as TaskEventType, payload, timestamp: '' });
                } catch {
                  // skip malformed events
                }
              }
            }
          }
        } catch (err) {
          if ((err as Error).name !== 'AbortError') {
            reject(err);
          }
        }
        resolve();
      })
      .catch(reject);
  });
}
