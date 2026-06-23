import { useEffect, useState } from 'react';
import { listActionAudits, type ActionAuditItem } from '../api/debug';

interface Props {
  accessToken: string;
}

const SOURCE_LABELS: Record<string, string> = {
  tool: 'Tool',
  browser: 'Browser',
  download: 'Download',
  local_agent: 'Local Agent',
  mcp: 'MCP',
};

const RISK_COLORS: Record<string, string> = {
  blocked: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  trusted: '#3b82f6',
  unknown: '#9ca3af',
};

export function ActionAuditPanel({ accessToken }: Props) {
  const [source, setSource] = useState('');
  const [items, setItems] = useState<ActionAuditItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    listActionAudits(accessToken, source || undefined)
      .then((data) => setItems(data.items ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [accessToken, source]);

  return (
    <section className="debug-panel">
      <h3>Action Audit</h3>
      <select value={source} onChange={(e) => setSource(e.target.value)}>
        <option value="">All</option>
        <option value="tool">Tool</option>
        <option value="browser">Browser</option>
        <option value="download">Download</option>
        <option value="local_agent">Local Agent</option>
        <option value="mcp">MCP</option>
      </select>
      {loading ? <p>Loading...</p> : null}
      {items.length === 0 ? (
        <p>No audit records.</p>
      ) : (
        items.map((item) => (
          <article key={item.id} className="audit-item">
            <strong>
              {SOURCE_LABELS[item.source] ?? item.source} / {item.action_type}
            </strong>
            <div>
              <span
                className="audit-risk"
                style={{ color: RISK_COLORS[item.risk_level] ?? '#9ca3af' }}
              >
                {item.status}
              </span>
              {' · risk: '}
              <span style={{ color: RISK_COLORS[item.risk_level] ?? '#9ca3af' }}>
                {item.risk_level}
              </span>
            </div>
            <div>
              {item.verified ? 'verified' : 'not verified'}
              {' · policy: '}
              {item.policy_allowed ? 'allowed' : 'blocked'}
            </div>
            <small>{item.target}</small>
          </article>
        ))
      )}
    </section>
  );
}
