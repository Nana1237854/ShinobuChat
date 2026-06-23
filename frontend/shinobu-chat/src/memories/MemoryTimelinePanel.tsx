import { useEffect, useMemo, useState } from 'react';
import { Archive, Clock3, Pin, Search, Trash2 } from 'lucide-react';
import { deleteMemory, getMemoryContext, getMemoryTimeline, searchMemories, updateMemory } from '../api/memories';
import type { MemoryContext, MemorySearchResult, MemoryTimelineItem } from '../types';

type MemoryTimelinePanelProps = {
  accessToken: string;
};

type PanelState = 'loading' | 'ready' | 'empty' | 'error';

type MemoryEntry = MemoryTimelineItem | MemorySearchResult;

const GROUP_ORDER = ['today', 'this_week', 'this_month', 'earlier'] as const;
const GROUP_LABELS: Record<string, string> = {
  today: '今天',
  this_week: '本周',
  this_month: '本月',
  earlier: '更早',
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function inferBucket(item: MemoryEntry) {
  return 'time_bucket' in item ? item.time_bucket : 'earlier';
}

export function MemoryTimelinePanel({ accessToken }: MemoryTimelinePanelProps) {
  const [query, setQuery] = useState('');
  const [timeline, setTimeline] = useState<MemoryTimelineItem[]>([]);
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [state, setState] = useState<PanelState>('loading');
  const [searchState, setSearchState] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'error'>('idle');
  const [contexts, setContexts] = useState<Record<string, MemoryContext | null>>({});
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const loadTimeline = async () => {
    setState('loading');
    setError(null);
    try {
      const result = await getMemoryTimeline(accessToken, { limit: 50, offset: 0 });
      setTimeline(result);
      setState(result.length ? 'ready' : 'empty');
    } catch (nextError) {
      setState('error');
      setError(nextError instanceof Error ? nextError.message : '无法加载记忆时间线');
    }
  };

  useEffect(() => {
    loadTimeline();
  }, [accessToken]);

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([]);
      setSearchState('idle');
      return;
    }

    const timer = window.setTimeout(async () => {
      setSearchState('loading');
      setError(null);
      try {
        const result = await searchMemories(accessToken, query.trim(), { limit: 12 });
        setSearchResults(result);
        setSearchState(result.length ? 'ready' : 'empty');
      } catch (nextError) {
        setSearchState('error');
        setError(nextError instanceof Error ? nextError.message : '搜索记忆失败');
      }
    }, 260);

    return () => window.clearTimeout(timer);
  }, [accessToken, query]);

  const entries = query.trim() ? searchResults : timeline;

  const groupedEntries = useMemo(() => {
    const groups = new Map<string, MemoryEntry[]>();
    for (const entry of entries) {
      const bucket = inferBucket(entry);
      if (!groups.has(bucket)) groups.set(bucket, []);
      groups.get(bucket)?.push(entry);
    }
    return groups;
  }, [entries]);

  const visibleGroupKeys = useMemo(() => {
    const existing = Array.from(groupedEntries.keys()).filter(Boolean);
    const ordered = GROUP_ORDER.filter(key => groupedEntries.has(key));
    const extras = existing.filter(key => !ordered.includes(key as typeof GROUP_ORDER[number]));
    return [...ordered, ...extras];
  }, [groupedEntries]);

  const toggleContext = async (memoryId: string) => {
    const isExpanded = expandedIds[memoryId];
    if (isExpanded) {
      setExpandedIds(current => ({ ...current, [memoryId]: false }));
      return;
    }

    setExpandedIds(current => ({ ...current, [memoryId]: true }));
    if (contexts[memoryId] !== undefined) return;

    try {
      const context = await getMemoryContext(accessToken, memoryId, { window: 3 });
      setContexts(current => ({ ...current, [memoryId]: context }));
    } catch {
      setContexts(current => ({ ...current, [memoryId]: null }));
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    if (!window.confirm('确定要永久删除这条记忆吗？此操作不可撤销。')) return;
    try {
      await deleteMemory(accessToken, memoryId);
      setTimeline(current => current.filter(m => m.memory_id !== memoryId));
      setSearchResults(current => current.filter(m => 'memory_id' in m && m.memory_id !== memoryId));
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    }
  };

  const handleTogglePin = async (memoryId: string, currentPinned: boolean) => {
    try {
      await updateMemory(accessToken, memoryId, { pinned: !currentPinned });
      setTimeline(current =>
        current.map(m => m.memory_id === memoryId ? { ...m, pinned: !currentPinned } : m),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
    }
  };

  const handleToggleArchive = async (memoryId: string) => {
    if (!window.confirm('归档这条记忆？归档后可从时间线隐藏。')) return;
    try {
      await updateMemory(accessToken, memoryId, { archived: true, archived_reason: 'user_manual' });
      setTimeline(current => current.filter(m => m.memory_id !== memoryId));
      setSearchResults(current => current.filter(m => !('memory_id' in m) || m.memory_id !== memoryId));
    } catch (e) {
      setError(e instanceof Error ? e.message : '归档失败');
    }
  };

  return (
    <section className="memory-panel" aria-label="记忆时间线">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Memory timeline</span>
          <h2>记忆时间线</h2>
          <p>按时间浏览 Shinobu 记住的长期内容。搜索和上下文回看都走真实接口，不在前端拼接假数据。</p>
        </div>
      </header>

      <div className="memory-search-bar">
        <Search size={16} />
        <input
          type="search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="搜索旧记忆，例如“旅行计划”或“工作节奏”"
          aria-label="搜索记忆"
        />
      </div>

      {error ? <p className="settings-status-error" aria-live="polite">{error}</p> : null}

      {state === 'loading' && !query.trim() ? (
        <div className="settings-skeleton"><span /><span /><span /></div>
      ) : null}

      {state === 'empty' && !query.trim() ? (
        <div className="settings-empty-state">
          <Clock3 size={30} />
          <h3>还没有长期记忆</h3>
          <p>这里会在后端存下足够内容后逐步出现，不会由前端补假记录。</p>
        </div>
      ) : null}

      {searchState === 'empty' && query.trim() ? (
        <div className="settings-empty-state">
          <Search size={30} />
          <h3>没有找到相关记忆</h3>
          <p>可以换个关键词试试，或清空搜索框返回时间线浏览。</p>
        </div>
      ) : null}

      {searchState === 'loading' ? (
        <div className="settings-skeleton"><span /><span /></div>
      ) : null}

      {(state === 'ready' || searchState === 'ready' || (query.trim() && searchState === 'error')) ? (
        <div className="memory-groups">
          {visibleGroupKeys.map(groupKey => {
            const items = groupedEntries.get(groupKey) || [];
            if (!items.length) return null;
            return (
              <section className="memory-group" key={groupKey}>
                <header>
                  <h3>{GROUP_LABELS[groupKey] || groupKey}</h3>
                </header>
                <div className="memory-list">
                  {items.map(item => {
                    const memoryId = item.memory_id;
                    const context = contexts[memoryId];
                    const expanded = Boolean(expandedIds[memoryId]);
                    return (
                      <article className="memory-card" key={memoryId}>
                        <div className="memory-card-top">
                          <span className="memory-importance">重要度 {Math.round(item.importance * 100)}%</span>
                          <time>{formatDate(item.created_at)}</time>
                        </div>
                        <p>{item.content}</p>
                        {'tags' in item && item.tags?.length ? (
                          <ul className="memory-tags" aria-label="记忆标签">
                            {item.tags.map(tag => <li key={tag}>{tag}</li>)}
                          </ul>
                        ) : null}
                        <div className="memory-actions">
                          <button type="button" className="settings-secondary-button" onClick={() => toggleContext(memoryId)}>
                            {expanded ? '收起上下文' : '查看上下文'}
                          </button>
                          <button
                            type="button"
                            className="settings-secondary-button"
                            title={item.pinned ? '取消置顶' : '置顶'}
                            onClick={() => handleTogglePin(memoryId, item.pinned ?? false)}
                          >
                            <Pin size={14} />
                            {item.pinned ? '已置顶' : '置顶'}
                          </button>
                          <button
                            type="button"
                            className="settings-secondary-button"
                            title="归档"
                            onClick={() => handleToggleArchive(memoryId)}
                          >
                            <Archive size={14} />
                            归档
                          </button>
                          <button
                            type="button"
                            className="settings-secondary-button settings-btn-danger"
                            title="删除记忆"
                            onClick={() => handleDeleteMemory(memoryId)}
                          >
                            <Trash2 size={14} />
                            删除记忆
                          </button>
                        </div>
                        {expanded ? (
                          <div className="memory-context">
                            {context === undefined ? <p>正在加载上下文…</p> : null}
                            {context === null ? <p>暂时无法加载这条记忆的上下文。</p> : null}
                            {context?.messages?.length ? (
                              context.messages.map(message => (
                                <div className="memory-context-item" key={message.id}>
                                  <strong>{message.role === 'assistant' ? 'Shinobu' : '你'}</strong>
                                  <p>{message.content}</p>
                                </div>
                              ))
                            ) : null}
                            {context?.detail ? <p className="memory-context-detail">{context.detail}</p> : null}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
