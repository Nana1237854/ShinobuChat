import { BellRing, Clock3, X } from 'lucide-react';
import type { ReminderEvent } from '../types';

type ReminderBubbleProps = {
  reminder: ReminderEvent;
  queuedCount: number;
  busy?: 'snooze' | 'dismiss' | null;
  onSnooze: (todoId: string) => void;
  onDismiss: (todoId: string) => void;
  onClose: (todoId: string) => void;
};

function formatDueAt(value: string | null) {
  if (!value) return '稍后提醒';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '稍后提醒';
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function ReminderBubble({
  reminder,
  queuedCount,
  busy = null,
  onSnooze,
  onDismiss,
  onClose,
}: ReminderBubbleProps) {
  return (
    <aside className="reminder-bubble" aria-live="polite" aria-label="Shinobu 提醒">
      <button
        type="button"
        className="reminder-bubble-close"
        title="关闭当前提醒"
        onClick={() => onClose(reminder.todo_id)}
      >
        <X size={15} />
      </button>

      <div className="reminder-bubble-badge">
        <BellRing size={14} />Shinobu 提醒
      </div>

      <h3>{reminder.title}</h3>
      <p>{reminder.message || '我来轻轻提醒你一下，这件事快到时间了。'}</p>

      <div className="reminder-bubble-meta">
        <span><Clock3 size={13} />{formatDueAt(reminder.due_at)}</span>
        {queuedCount > 0 ? <strong>还有 {queuedCount} 条等待提醒</strong> : null}
      </div>

      <div className="reminder-bubble-actions">
        <button
          type="button"
          className="settings-secondary-button"
          onClick={() => onSnooze(reminder.todo_id)}
          disabled={busy !== null}
        >
          {busy === 'snooze' ? '稍后提醒中' : '稍后提醒'}
        </button>
        <button
          type="button"
          className="settings-primary-button"
          onClick={() => onDismiss(reminder.todo_id)}
          disabled={busy !== null}
        >
          {busy === 'dismiss' ? '处理中' : '完成 / 忽略'}
        </button>
      </div>
    </aside>
  );
}
