import { AlertTriangle, ShieldCheck, ShieldOff } from 'lucide-react';
import RiskBadge from './RiskBadge';
import type { ClassifiedDownload } from '../../api/browser';

interface Props {
  candidates: ClassifiedDownload[];
  busy?: boolean;
}

export default function DownloadCandidateList({ candidates, busy }: Props) {
  if (candidates.length === 0) {
    return <p className="settings-empty-state">没有发现下载候选。</p>;
  }

  return (
    <section className="download-candidate-list" aria-label="下载候选列表">
      {candidates.map((c, i) => (
        <article
          key={i}
          className={`download-candidate-card download-candidate-card--${c.risk_level}`}
          aria-label={`下载候选: ${c.text}`}
        >
          <div className="download-candidate-card__header">
            <span className="download-candidate-card__text">{c.text}</span>
            <RiskBadge level={c.risk_level} />
          </div>

          <p className="download-candidate-card__url">{c.href}</p>

          <div className="download-candidate-card__meta">
            <span>域名: {c.domain || '未知'}</span>
            <span>类型: {c.extension || '未知'}</span>
          </div>

          {c.reasons.length > 0 && (
            <ul className="download-candidate-card__reasons">
              {c.reasons.map((r, j) => (
                <li key={j}>检测: {r}</li>
              ))}
            </ul>
          )}

          <div className="download-candidate-card__suggestion">
            {c.risk_level === 'blocked' && (
              <p className="download-candidate-card__blocked-msg">
                <ShieldOff size={14} /> 该链接已被安全策略阻止，不能自动下载。
              </p>
            )}
            {c.risk_level === 'high' && (
              <p className="download-candidate-card__risk-msg">
                <AlertTriangle size={14} /> 该链接来源或文件类型存在风险，系统不会自动点击。建议你手动确认来源。
              </p>
            )}
            {c.risk_level === 'trusted' && c.requires_confirmation && (
              <p className="download-candidate-card__trusted-exe-msg">
                <ShieldCheck size={14} /> 该来源在可信列表中，但文件是可执行安装包，下载前仍需要你确认。
              </p>
            )}
            <span className="download-candidate-card__action-hint">
              建议: {c.suggested_action}
            </span>
          </div>

          {busy && (
            <div className="download-candidate-card__busy">处理中...</div>
          )}
        </article>
      ))}
    </section>
  );
}
