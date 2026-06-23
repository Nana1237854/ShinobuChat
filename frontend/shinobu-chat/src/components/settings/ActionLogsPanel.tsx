import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import {
  getLocalActionLogs,
  getBrowserActionLogs,
  type ActionLogEntry,
  type BrowserActionLogEntry,
} from '../../api/actionLogs';

interface Props {
  accessToken: string;
}

const STATUS_LABELS: Record<string, string> = {
  opened: '已打开',
  failed: '失败',
  started: '已开始',
  ok: '成功',
  error: '错误',
  cancelled: '已取消',
};

export default function ActionLogsPanel({ accessToken }: Props) {
  const [localLogs, setLocalLogs] = useState<ActionLogEntry[]>([]);
  const [browserLogs, setBrowserLogs] = useState<BrowserActionLogEntry[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterAction, setFilterAction] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const refresh = useCallback(async () => {
    setLoadState('loading');
    try {
      const [local, browser] = await Promise.all([
        getLocalActionLogs(accessToken, { limit: 50 }),
        getBrowserActionLogs(accessToken, { limit: 50 }),
      ]);
      setLocalLogs(local.logs ?? []);
      setBrowserLogs(browser.logs ?? []);
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  }, [accessToken]);

  useEffect(() => { refresh(); }, [refresh]);

  const filteredLocal = localLogs.filter((l) => {
    if (filterAction && l.action_type !== filterAction) return false;
    if (filterStatus && l.status !== filterStatus) return false;
    return true;
  });

  const filteredBrowser = browserLogs.filter((l) => {
    if (filterAction && l.action_type !== filterAction) return false;
    if (filterStatus && l.status !== filterStatus) return false;
    return true;
  });

  const allActions = [...new Set([
    ...localLogs.map((l) => l.action_type),
    ...browserLogs.map((l) => l.action_type),
  ])];
  const allStatuses = [...new Set([
    ...localLogs.map((l) => l.status),
    ...browserLogs.map((l) => l.status),
  ])];

  return (
    <section className="action-logs-panel" aria-label="执行日志">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Action Logs</span>
          <h2>执行日志</h2>
          <p>本地动作和浏览器动作记录</p>
        </div>
        <button
          className="settings-primary-button"
          onClick={refresh}
          aria-label="刷新日志"
        >
          <RefreshCw size={15} /> 刷新日志
        </button>
      </header>

      {/* Filters */}
      <div className="action-logs-filters">
        <select
          className="settings-input"
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          aria-label="筛选动作类型"
        >
          <option value="">全部类型</option>
          {allActions.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        <select
          className="settings-input"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          aria-label="筛选状态"
        >
          <option value="">全部状态</option>
          {allStatuses.map((s) => (
            <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
          ))}
        </select>
      </div>

      {loadState === 'loading' && (
        <div className="settings-skeleton"><span /><span /><span /></div>
      )}
      {loadState === 'error' && (
        <p className="settings-status-error">无法加载日志。</p>
      )}

      {loadState === 'ready' && (
        <>
          {/* Local action logs */}
          <div className="action-logs-section">
            <h3>本地动作日志 ({filteredLocal.length})</h3>
            {filteredLocal.length === 0 ? (
              <p className="settings-empty-state">暂无本地动作日志。</p>
            ) : (
              <div className="action-logs-table">
                <div className="action-logs-table-header">
                  <span>时间</span>
                  <span>动作</span>
                  <span>目标</span>
                  <span>状态</span>
                  <span />
                </div>
                {filteredLocal.map((log) => (
                  <div key={log.id} className="action-logs-row">
                    <span className="action-logs-time">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                    <span className="action-logs-action">{log.action_type}</span>
                    <span className="action-logs-target">{log.target}</span>
                    <span className={`action-logs-status action-logs-status--${log.status}`}>
                      {STATUS_LABELS[log.status] ?? log.status}
                    </span>
                    <button
                      className="settings-secondary-button"
                      onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                      aria-label="展开详情"
                    >
                      {expandedId === log.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    {expandedId === log.id && (
                      <div className="action-logs-detail">
                        {log.message && <p>消息: {log.message}</p>}
                        {log.error_detail && <p className="action-logs-error">错误: {log.error_detail}</p>}
                        {log.finished_at && <p>完成时间: {new Date(log.finished_at).toLocaleString()}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Browser action logs */}
          <div className="action-logs-section">
            <h3>浏览器动作日志 ({filteredBrowser.length})</h3>
            {filteredBrowser.length === 0 ? (
              <p className="settings-empty-state">暂无浏览器动作日志。</p>
            ) : (
              <div className="action-logs-table">
                <div className="action-logs-table-header">
                  <span>时间</span>
                  <span>动作</span>
                  <span>目标 URL</span>
                  <span>状态</span>
                  <span />
                </div>
                {filteredBrowser.map((log) => (
                  <div key={log.id} className="action-logs-row">
                    <span className="action-logs-time">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                    <span className="action-logs-action">{log.action_type}</span>
                    <span className="action-logs-target">{log.target_url || '-'}</span>
                    <span className={`action-logs-status action-logs-status--${log.status}`}>
                      {STATUS_LABELS[log.status] ?? log.status}
                    </span>
                    <button
                      className="settings-secondary-button"
                      onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                      aria-label="展开详情"
                    >
                      {expandedId === log.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    {expandedId === log.id && (
                      <div className="action-logs-detail">
                        {log.message && <p>消息: {log.message}</p>}
                        {log.error_detail && <p className="action-logs-error">错误: {log.error_detail}</p>}
                        {log.finished_at && <p>完成时间: {new Date(log.finished_at).toLocaleString()}</p>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
