import { useState } from 'react';
import { ChevronDown, Clock3, Play, X, Check } from 'lucide-react';
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

  if (logs.length === 0) return null;

  const lastFailed = logs[logs.length - 1]?.status === 'failed';

  return (
    <section
      className={`action-progress-panel ${expanded ? 'is-expanded' : 'is-collapsed'}${lastFailed ? ' has-failed' : ''}`}
      aria-label="本地操作执行进度"
    >
      <button
        type="button"
        className="action-progress-header"
        onClick={toggle}
        aria-expanded={expanded}
      >
        <ChevronDown
          size={14}
          className={`action-progress-chevron ${expanded ? 'is-open' : ''}`}
        />
        <span className="action-progress-title">本地操作日志</span>
        <span className="action-progress-count">{logs.length}</span>
      </button>

      {expanded ? (
        <div className="action-progress-log-list" role="log">
          {logs.map((entry, i) => {
            const Icon = statusIcons[entry.status] || Clock3;
            return (
              <div
                key={`${entry.timestamp}-${i}`}
                className={`action-progress-log-row status-${entry.status}`}
              >
                <span className="action-progress-time">
                  {formatTimestamp(entry.timestamp)}
                </span>
                <span className="action-progress-target">
                  <Icon size={11} />
                  <span>{entry.displayName || entry.appKey || ''}</span>
                </span>
                <span className="action-progress-message">
                  {entry.message}
                </span>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
