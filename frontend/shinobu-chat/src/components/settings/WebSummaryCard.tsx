import { ExternalLink } from 'lucide-react';
import type { BrowserSummarizeResult } from '../../api/browser';

interface Props {
  result: BrowserSummarizeResult;
}

export default function WebSummaryCard({ result }: Props) {
  return (
    <article className="web-summary-card" aria-label="网页总结">
      <h3 className="web-summary-card__title">网页总结</h3>
      {result.source_url && (
        <a
          href={result.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="web-summary-card__url"
        >
          <ExternalLink size={12} /> {result.source_url}
        </a>
      )}

      {result.summary && (
        <p className="web-summary-card__summary">{result.summary}</p>
      )}

      {result.key_points.length > 0 && (
        <ul className="web-summary-card__points">
          {result.key_points.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      )}
    </article>
  );
}
