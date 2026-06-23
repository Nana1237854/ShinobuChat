import { ExternalLink, BookOpen, Sparkles } from 'lucide-react';
import type { SearchResult } from '../../api/browser';

interface Props {
  result: SearchResult;
  onRead: (url: string) => void;
  onSummarize: (url: string) => void;
  onOpen: (url: string) => void;
}

export default function WebSearchCard({ result, onRead, onSummarize, onOpen }: Props) {
  return (
    <article className="web-search-card" aria-label={`搜索结果: ${result.title}`}>
      <h3 className="web-search-card__title">{result.title}</h3>
      <p className="web-search-card__url">{result.url}</p>
      {result.snippet && (
        <p className="web-search-card__snippet">{result.snippet}</p>
      )}
      <div className="web-search-card__actions">
        <button
          className="settings-secondary-button"
          onClick={() => onOpen(result.url)}
          aria-label="打开 URL"
        >
          <ExternalLink size={14} /> 打开
        </button>
        <button
          className="settings-secondary-button"
          onClick={() => onRead(result.url)}
          aria-label="读取网页"
        >
          <BookOpen size={14} /> 读取
        </button>
        <button
          className="settings-secondary-button"
          onClick={() => onSummarize(result.url)}
          aria-label="总结网页"
        >
          <Sparkles size={14} /> 总结
        </button>
      </div>
    </article>
  );
}
