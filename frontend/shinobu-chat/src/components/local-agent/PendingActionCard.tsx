import { useEffect, useState } from 'react';
import { Check, X, Clock3 } from 'lucide-react';
import { confirmPendingAction, cancelPendingAction } from '../../api/pendingActions';
import type { PendingAction } from '../../types';

type PendingActionCardProps = {
  accessToken: string;
  action: PendingAction;
  onResolved: () => void;
};

function computeRemainingSeconds(expiresAt: string | null | undefined): number | null {
  if (!expiresAt) return null;
  const remaining = Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 1000));
  return remaining;
}

function formatTimeLeft(seconds: number): string {
  if (seconds <= 0) return '已过期';
  if (seconds < 60) return `${seconds} 秒`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分钟`;
}

export function PendingActionCard({ accessToken, action, onResolved }: PendingActionCardProps) {
  const [remaining, setRemaining] = useState<number | null>(() =>
    computeRemainingSeconds(action.expires_at),
  );
  const [busy, setBusy] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    const timer = setInterval(() => {
      const next = computeRemainingSeconds(action.expires_at);
      setRemaining(next);
      if (next !== null && next <= 0) {
        clearInterval(timer);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [action.expires_at, remaining]);

  // Auto-dismiss when expired
  useEffect(() => {
    if (remaining !== null && remaining <= 0) {
      const timeout = setTimeout(() => onResolved(), 2000);
      return () => clearTimeout(timeout);
    }
  }, [remaining, onResolved]);

  // Auto-dismiss if already resolved
  useEffect(() => {
    if (action.status !== 'waiting_confirmation') {
      const timeout = setTimeout(() => onResolved(), 3000);
      return () => clearTimeout(timeout);
    }
  }, [action.status, onResolved]);

  const handleConfirm = async () => {
    if (!action.id) {
      setResultMessage('无法确认：缺少 pending action id');
      return;
    }
    setBusy(true);
    try {
      const result = await confirmPendingAction(accessToken, action.id);
      setResultMessage(result.result_message || '已确认执行');
    } catch {
      // Backend may have already resolved it; dismiss the card regardless
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    if (!action.id) {
      setResultMessage('无法取消：缺少 pending action id');
      return;
    }
    setBusy(true);
    try {
      await cancelPendingAction(accessToken, action.id);
      setResultMessage('已取消');
    } catch {
      // Backend may have already resolved it; dismiss the card regardless
    } finally {
      setBusy(false);
    }
  };

  const expired = remaining !== null && remaining <= 0;
  const isResolved = action.status !== 'waiting_confirmation' || resultMessage !== null;

  return (
    <div className={['pending-action-card', expired ? 'is-expired' : '', isResolved ? 'is-resolved' : ''].filter(Boolean).join(' ')} aria-live="polite">
      <div className="pending-action-icon">
        <Clock3 size={18} />
      </div>
      <div className="pending-action-body">
        <p className="pending-action-description">{action.description || `${action.display_name || action.app_key || '应用'} 请求你的确认`}</p>
        {action.display_name ? (
          <span className="pending-action-app-name">{action.display_name}</span>
        ) : null}
        <div className="pending-action-meta">
          {remaining !== null && !expired && !isResolved ? (
            <span className="pending-action-countdown">
              <Clock3 size={12} />
              {formatTimeLeft(remaining)}
            </span>
          ) : null}
          {resultMessage ? (
            <span className="pending-action-result">{resultMessage}</span>
          ) : null}
          {expired ? (
            <span className="pending-action-expired">已过期，即将消失</span>
          ) : null}
        </div>
      </div>
      {!isResolved && !expired ? (
        <div className="pending-action-actions">
          <button
            type="button"
            className="pending-action-confirm-btn"
            onClick={handleConfirm}
            disabled={busy}
            title="确认"
          >
            <Check size={16} />
          </button>
          <button
            type="button"
            className="pending-action-cancel-btn"
            onClick={handleCancel}
            disabled={busy}
            title="取消"
          >
            <X size={16} />
          </button>
        </div>
      ) : null}
      {isResolved ? (
        <button type="button" className="pending-action-dismiss-btn" onClick={onResolved} title="关闭">
          <X size={14} />
        </button>
      ) : null}
    </div>
  );
}
