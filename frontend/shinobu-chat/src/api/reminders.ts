import type { ReminderEvent } from '../types';
import { requestJson } from './http';

export function getDueReminders(accessToken: string): Promise<ReminderEvent[]> {
  return requestJson<ReminderEvent[]>('/reminders/due', { accessToken });
}

export function snoozeReminder(
  accessToken: string,
  todoId: string,
  minutes = 10,
): Promise<ReminderEvent> {
  return requestJson<ReminderEvent>(`/reminders/${encodeURIComponent(todoId)}/snooze`, {
    method: 'POST',
    accessToken,
    body: { minutes },
  });
}

export function dismissReminder(
  accessToken: string,
  todoId: string,
): Promise<ReminderEvent> {
  return requestJson<ReminderEvent>(`/reminders/${encodeURIComponent(todoId)}/dismiss`, {
    method: 'POST',
    accessToken,
  });
}
