import { useState } from 'react';
import { ChevronDown, ChevronRight, Clock3, Play, X, Check } from 'lucide-react';
import type { ActionLogEntry } from '../../types';

type ActionProgressPanelProps = {
  logs: ActionLogEntry[];
  expanded?: boolean;
  onToggleExpand?: () => void;
};

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const statusIcons: Record<ActionLogEntry['status'], typeof Play> = {
  starting: Clock3,
  running: Play,
  completed: Check,
  failed: X,
  cancelled: X,
};

export function ActionProgressPanel({ logs, expanded: externalExpanded, onToggleExpand }: ActionProgressPanelProps) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = externalExpanded ?? internalExpanded;

  const toggle = () => {
    if (onToggleExpand) {
      onToggleExpand();
    } else {
      setInternalExpanded(current => !current);
    }
  };

  const recentLogs = expanded ? logs : logs.slice(-3);

  if (logs.length === 0) return null;

  return (
    <div className="action-progress-panel" aria-label="本地操作执行进度">
      <button type="button" className="action-progress-toggle" onClick={toggle}>
        <span className="action-progress-toggle-icon">
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span className="action-progress-toggle-label">
          本地操作日志
          <span className="action-progress-count">{logs.length}</span>
        </span>
      </button>

      {expanded ? (
        <div className="action-progress-log-list">
          {recentLogs.map((entry, i) => {
            const Icon = statusIcons[entry.status] || Clock3;
            return (
              <div
                key={`${entry.timestamp}-${i}`}
                className={['action-progress-entry', `status-${entry.status}`].join(' ')}
              >
                <span className="action-progress-entry-icon">
                  <Icon size={13} />
                </span>
                <span className="action-progress-entry-time">
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className="action-progress-entry-app">
                  {entry.displayName || entry.appKey || ''}
                </span>
                <span className="action-progress-entry-msg">
                  {entry.message}
                </span>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
