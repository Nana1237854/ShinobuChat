import type { ReminderEvent } from '../types';

const SYNC_DEVICE_KEY = 'shinobu-sync-device-id';

function getSyncDeviceId() {
  const existing = window.localStorage.getItem(SYNC_DEVICE_KEY);
  if (existing) return existing;

  const generated = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `web-${Date.now()}`;

  window.localStorage.setItem(SYNC_DEVICE_KEY, generated);
  return generated;
}

function parseReminderPayload(data: string): ReminderEvent | null {
  try {
    return JSON.parse(data) as ReminderEvent;
  } catch {
    return null;
  }
}

export function subscribeReminderEvents(options: {
  userId: string;
  onReminder: (event: ReminderEvent) => void;
  onError?: () => void;
}) {
  const url = new URL('/api/v1/sync/events', window.location.origin);
  url.searchParams.set('user_id', options.userId);
  url.searchParams.set('device_id', getSyncDeviceId());
  url.searchParams.set('device_type', 'web');

  const source = new EventSource(url.toString());
  const handleReminder = (event: MessageEvent<string>) => {
    const payload = parseReminderPayload(event.data);
    if (payload) options.onReminder(payload);
  };

  source.addEventListener('reminder.due_soon', handleReminder as EventListener);
  source.addEventListener('reminder.due_now', handleReminder as EventListener);
  source.onerror = () => {
    options.onError?.();
  };

  return () => {
    source.removeEventListener('reminder.due_soon', handleReminder as EventListener);
    source.removeEventListener('reminder.due_now', handleReminder as EventListener);
    source.close();
  };
}
