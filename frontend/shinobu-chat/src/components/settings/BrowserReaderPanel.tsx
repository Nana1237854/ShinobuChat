import { useState } from 'react';
import { Search, BookOpen, Sparkles, Globe } from 'lucide-react';
import {
  searchWeb,
  readWebPage,
  summarizeWebPage,
  extractDownloadCandidates,
  classifyDownloads,
  openUrl,
  type SearchResult,
  type BrowserReadResult,
  type BrowserSummarizeResult,
  type ClassifiedDownload,
} from '../../api/browser';
import WebSearchCard from './WebSearchCard';
import WebReadResult from './WebReadResult';
import WebSummaryCard from './WebSummaryCard';
import DownloadCandidateList from './DownloadCandidateList';

interface Props {
  accessToken: string;
}

type ViewMode = 'search' | 'read' | 'summarize';

export default function BrowserReaderPanel({ accessToken }: Props) {
  const [mode, setMode] = useState<ViewMode>('search');
  const [query, setQuery] = useState('');
  const [url, setUrl] = useState('');
  const [question, setQuestion] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [readResult, setReadResult] = useState<BrowserReadResult | null>(null);
  const [summaryResult, setSummaryResult] = useState<BrowserSummarizeResult | null>(null);
  const [classifiedDownloads, setClassifiedDownloads] = useState<ClassifiedDownload[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clear = () => {
    setError(null);
    setSearchResults([]);
    setReadResult(null);
    setSummaryResult(null);
    setClassifiedDownloads([]);
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    clear();
    setBusy(true);
    try {
      const res = await searchWeb(accessToken, query);
      if (res.status === 'ok') {
        setSearchResults(res.results);
      } else {
        setError(res.message || '搜索失败');
      }
    } catch (e) {
      setError(`搜索请求失败: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const handleRead = async (targetUrl: string) => {
    clear();
    setBusy(true);
    try {
      const res = await readWebPage(accessToken, targetUrl);
      if (res.status === 'ok') {
        setReadResult(res);
      } else {
        setError(res.message || '读取失败');
      }
    } catch (e) {
      setError(`读取请求失败: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSummarize = async (targetUrl: string) => {
    clear();
    setBusy(true);
    try {
      const res = await summarizeWebPage(accessToken, targetUrl, question || '这个页面主要讲了什么？');
      if (res.status === 'ok') {
        setSummaryResult(res);
      } else {
        setError(res.message || '总结失败');
      }
    } catch (e) {
      setError(`总结请求失败: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const handleExtractCandidates = async (targetUrl: string) => {
    setError(null);
    setBusy(true);
    try {
      const extractRes = await extractDownloadCandidates(accessToken, targetUrl);
      if (extractRes.status !== 'ok' || extractRes.candidates.length === 0) {
        setError(extractRes.message || '没有发现下载候选');
        setBusy(false);
        return;
      }
      const classifyRes = await classifyDownloads(accessToken, extractRes.candidates);
      if (classifyRes.status === 'ok') {
        setClassifiedDownloads(classifyRes.classified);
      } else {
        setError(classifyRes.message || '分类失败');
      }
    } catch (e) {
      setError(`下载分析失败: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const handleOpenUrl = async (targetUrl: string) => {
    try {
      const res = await openUrl(accessToken, targetUrl);
      if (res.status !== 'ok') {
        setError(res.message || '打开失败');
      }
    } catch (e) {
      setError(`打开URL失败: ${e}`);
    }
  };

  return (
    <section className="browser-reader-panel" aria-label="浏览器能力">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Browser Reader</span>
          <h2>浏览器能力</h2>
          <p>搜索网页、读取内容、总结摘要</p>
        </div>
      </header>

      {/* Mode tabs */}
      <nav className="browser-reader-tabs" aria-label="浏览器操作模式">
        <button
          className={`settings-secondary-button ${mode === 'search' ? 'active' : ''}`}
          onClick={() => { setMode('search'); clear(); }}
        >
          <Search size={14} /> 搜索网页
        </button>
        <button
          className={`settings-secondary-button ${mode === 'read' ? 'active' : ''}`}
          onClick={() => { setMode('read'); clear(); }}
        >
          <BookOpen size={14} /> 读取网页
        </button>
        <button
          className={`settings-secondary-button ${mode === 'summarize' ? 'active' : ''}`}
          onClick={() => { setMode('summarize'); clear(); }}
        >
          <Sparkles size={14} /> 总结网页
        </button>
      </nav>

      {/* Search mode */}
      {mode === 'search' && (
        <div className="browser-reader-input-area">
          <input
            type="text"
            className="settings-input"
            placeholder="输入搜索关键词，如：网易云音乐 Windows 官网下载"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            aria-label="搜索关键词"
          />
          <button
            className="settings-primary-button"
            onClick={handleSearch}
            disabled={busy || !query.trim()}
            aria-label="搜索网页"
          >
            <Search size={14} /> 搜索网页
          </button>
        </div>
      )}

      {/* Read mode */}
      {mode === 'read' && (
        <div className="browser-reader-input-area">
          <input
            type="text"
            className="settings-input"
            placeholder="输入 URL，如：https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRead(url)}
            aria-label="网页 URL"
          />
          <button
            className="settings-primary-button"
            onClick={() => handleRead(url)}
            disabled={busy || !url.trim()}
            aria-label="读取网页"
          >
            <Globe size={14} /> 读取网页
          </button>
        </div>
      )}

      {/* Summarize mode */}
      {mode === 'summarize' && (
        <div className="browser-reader-input-area browser-reader-input-area--col">
          <input
            type="text"
            className="settings-input"
            placeholder="输入 URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="要总结的网页 URL"
          />
          <input
            type="text"
            className="settings-input"
            placeholder="问题（可选），如：这个页面主要讲了什么？"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            aria-label="总结问题"
          />
          <button
            className="settings-primary-button"
            onClick={() => handleSummarize(url)}
            disabled={busy || !url.trim()}
            aria-label="总结网页"
          >
            <Sparkles size={14} /> 总结网页
          </button>
        </div>
      )}

      {/* Busy indicator */}
      {busy && (
        <div className="settings-skeleton" aria-label="加载中">
          <span /><span /><span />
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="settings-status-error" role="alert">{error}</p>
      )}

      {/* Search results */}
      {searchResults.length > 0 && (
        <div className="browser-reader-results">
          {searchResults.map((r, i) => (
            <WebSearchCard
              key={i}
              result={r}
              onRead={handleRead}
              onSummarize={handleSummarize}
              onOpen={handleOpenUrl}
            />
          ))}
        </div>
      )}

      {/* Read result */}
      {readResult && (
        <WebReadResult
          result={readResult}
          onExtractCandidates={handleExtractCandidates}
        />
      )}

      {/* Summary result */}
      {summaryResult && <WebSummaryCard result={summaryResult} />}

      {/* Download candidates */}
      {classifiedDownloads.length > 0 && (
        <DownloadCandidateList candidates={classifiedDownloads} busy={busy} />
      )}

      {/* Empty state */}
      {!busy && !error && !searchResults.length && !readResult && !summaryResult && !classifiedDownloads.length && (
        <p className="settings-empty-state">
          {mode === 'search' && '输入关键词后点击"搜索网页"开始搜索。'}
          {mode === 'read' && '输入 URL 后点击"读取网页"获取页面内容。'}
          {mode === 'summarize' && '输入 URL 后点击"总结网页"获取 AI 总结。'}
        </p>
      )}
    </section>
  );
}
