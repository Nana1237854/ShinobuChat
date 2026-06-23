import { useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react';
import type { BrowserReadResult } from '../../api/browser';

interface Props {
  result: BrowserReadResult;
  onExtractCandidates?: (url: string) => void;
}

export default function WebReadResult({ result, onExtractCandidates }: Props) {
  const [showLinks, setShowLinks] = useState(false);
  const links = result.links ?? [];

  return (
    <article className="web-read-result" aria-label={`网页内容: ${result.title}`}>
      <h3 className="web-read-result__title">{result.title}</h3>
      <p className="web-read-result__url">{result.url}</p>

      {result.content && (
        <div className="web-read-result__content">
          <pre>{result.content.slice(0, 2000)}</pre>
          {result.content.length > 2000 && (
            <p className="web-read-result__truncated">... 内容已截断（显示前2000字符）</p>
          )}
        </div>
      )}

      {links.length > 0 && (
        <div className="web-read-result__links">
          <button
            className="settings-secondary-button"
            onClick={() => setShowLinks(!showLinks)}
            aria-label={showLinks ? '折叠链接' : '展开链接'}
          >
            {showLinks ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            链接 ({links.length})
          </button>
          {showLinks && (
            <ul className="web-read-result__link-list">
              {links.slice(0, 50).map((link, i) => (
                <li key={i}>
                  <a
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="web-read-result__link-item"
                  >
                    <ExternalLink size={12} /> {link.text || link.href}
                  </a>
                </li>
              ))}
              {links.length > 50 && <li>... 还有 {links.length - 50} 个链接</li>}
            </ul>
          )}
        </div>
      )}

      {onExtractCandidates && links.length > 0 && (
        <div className="web-read-result__extract">
          <button
            className="settings-primary-button"
            onClick={() => onExtractCandidates(result.url)}
            aria-label="提取下载候选"
          >
            提取下载候选
          </button>
        </div>
      )}
    </article>
  );
}
