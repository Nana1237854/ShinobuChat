import { useCallback, useEffect, useMemo, useState } from 'react';
import { BookOpen, Calendar, ChevronLeft, ChevronRight, RefreshCw, Sparkles, X } from 'lucide-react';
import { exportDiaries, generateDiary, getDiaryByDate, listDiaries } from '../api/diaries';
import { ApiRequestError } from '../api/http';
import type { DiaryDetail, DiaryItem } from '../types';

type PanelState = 'loading' | 'ready' | 'empty' | 'error';

const MOOD_EMOJI: Record<string, string> = {
  happy: '\u{1F60A}',
  worried: '\u{1F61F}',
  stressed: '\u{1F630}',
  tired: '\u{1F634}',
  lonely: '\u{1F97A}',
  neutral: '\u{1F610}',
};

const DAY_NAMES = ['一', '二', '三', '四', '五', '六', '日'];

function formatDateChinese(dateStr: string): string {
  const parts = dateStr.split('-').map(Number);
  if (parts.length !== 3 || parts.some(isNaN)) return dateStr;
  return `${parts[0]}年${parts[1]}月${parts[2]}日`;
}

function getToday(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function getMonthDays(year: number, month: number) {
  const firstDay = new Date(year, month - 1, 1);
  const lastDay = new Date(year, month, 0);
  const daysInMonth = lastDay.getDate();
  const jsDayOfWeek = firstDay.getDay(); // 0 = Sunday
  const startOffset = jsDayOfWeek === 0 ? 6 : jsDayOfWeek - 1;

  const days: { date: string; day: number; isCurrentMonth: boolean }[] = [];

  // Previous month padding
  const prevMonthLastDay = new Date(year, month - 1, 0).getDate();
  for (let i = startOffset - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i;
    const prevM = month === 1 ? 12 : month - 1;
    const prevY = month === 1 ? year - 1 : year;
    days.push({
      date: `${prevY}-${String(prevM).padStart(2, '0')}-${String(d).padStart(2, '0')}`,
      day: d,
      isCurrentMonth: false,
    });
  }

  // Current month
  for (let i = 1; i <= daysInMonth; i++) {
    days.push({
      date: `${year}-${String(month).padStart(2, '0')}-${String(i).padStart(2, '0')}`,
      day: i,
      isCurrentMonth: true,
    });
  }

  // Next month padding
  const remaining = 7 - (days.length % 7);
  if (remaining < 7) {
    const nextM = month === 12 ? 1 : month + 1;
    const nextY = month === 12 ? year + 1 : year;
    for (let i = 1; i <= remaining; i++) {
      days.push({
        date: `${nextY}-${String(nextM).padStart(2, '0')}-${String(i).padStart(2, '0')}`,
        day: i,
        isCurrentMonth: false,
      });
    }
  }

  return days;
}

export function DiaryPanel({ accessToken }: { accessToken: string }) {
  const [diaries, setDiaries] = useState<DiaryItem[]>([]);
  const [state, setState] = useState<PanelState>('loading');
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [detail, setDetail] = useState<DiaryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [currentYear, setCurrentYear] = useState(() => new Date().getFullYear());
  const [currentMonth, setCurrentMonth] = useState(() => new Date().getMonth() + 1);

  const today = getToday();

  const loadDiaries = useCallback(async () => {
    setState('loading');
    setError(null);
    try {
      const result = await listDiaries(accessToken, { limit: 100, offset: 0 });
      setDiaries(result);
      setState(result.length ? 'ready' : 'empty');
    } catch (e) {
      setState('error');
      setError(e instanceof Error ? e.message : '无法加载日记列表');
    }
  }, [accessToken]);

  useEffect(() => {
    loadDiaries();
  }, [loadDiaries]);

  const sortedDiaries = useMemo(() => {
    return [...diaries].sort((a, b) => b.date.localeCompare(a.date));
  }, [diaries]);

  const diaryDates = useMemo(() => {
    return new Set(diaries.map(d => d.date));
  }, [diaries]);

  const monthDays = useMemo(() => {
    return getMonthDays(currentYear, currentMonth);
  }, [currentYear, currentMonth]);

  const handlePrevMonth = useCallback(() => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(y => y - 1);
    } else {
      setCurrentMonth(m => m - 1);
    }
  }, [currentMonth]);

  const handleNextMonth = useCallback(() => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(y => y + 1);
    } else {
      setCurrentMonth(m => m + 1);
    }
  }, [currentMonth]);

  const handleSelectDate = useCallback(async (date: string) => {
    if (selectedDate === date) {
      setSelectedDate(null);
      setDetail(null);
      setDetailError(null);
      return;
    }

    setSelectedDate(date);
    setDetail(null);
    setDetailError(null);

    if (!diaryDates.has(date)) return;

    setDetailLoading(true);
    try {
      const result = await getDiaryByDate(accessToken, date);
      setDetail(result);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : '无法加载日记详情');
    } finally {
      setDetailLoading(false);
    }
  }, [accessToken, diaryDates, selectedDate]);

  const handleSelectDiaryItem = useCallback(async (item: DiaryItem) => {
    if (selectedDate === item.date) {
      setSelectedDate(null);
      setDetail(null);
      setDetailError(null);
      return;
    }

    setSelectedDate(item.date);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    try {
      const result = await getDiaryByDate(accessToken, item.date);
      setDetail(result);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : '无法加载日记详情');
    } finally {
      setDetailLoading(false);
    }
  }, [accessToken, selectedDate]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateDiary(accessToken, { date: today });
      loadDiaries();
      setSelectedDate(result.date);
      setDetail({
        diary_id: result.diary_id,
        date: result.date,
        title: result.title,
        summary: result.summary,
        mood: result.mood ?? null,
        content: result.content,
        tags: result.tags,
        source_conversation_ids: [],
        created_at: new Date().toISOString(),
      });
      setState('ready');
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 501) {
        setError('日记生成功能即将支持，敬请期待。');
      } else {
        setError(e instanceof Error ? e.message : '生成日记失败');
      }
    } finally {
      setGenerating(false);
    }
  }, [accessToken, today, loadDiaries]);

  const handleForceRegenerate = useCallback(async () => {
    if (!selectedDate) return;
    setGenerating(true);
    setError(null);
    try {
      await generateDiary(accessToken, { date: selectedDate, force: true });
      await loadDiaries();
      const result = await getDiaryByDate(accessToken, selectedDate);
      setDetail(result);
    } catch (e) {
      if (e instanceof ApiRequestError && e.status === 501) {
        setError('日记生成功能即将支持，敬请期待。');
      } else {
        setError(e instanceof Error ? e.message : '重新生成失败');
      }
    } finally {
      setGenerating(false);
    }
  }, [accessToken, selectedDate, loadDiaries]);

  const closeDetail = useCallback(() => {
    setSelectedDate(null);
    setDetail(null);
    setDetailError(null);
  }, []);

  const handleExport = useCallback(async () => {
    setError(null);
    try {
      const toDate = today;
      const fromDate = `${currentYear}-${String(currentMonth).padStart(2, '0')}-01`;
      const { text, filename } = await exportDiaries(accessToken, fromDate, toDate);
      const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : '导出失败');
    }
  }, [accessToken, today, currentYear, currentMonth]);

  const monthLabel = `${currentYear}年${currentMonth}月`;

  return (
    <section className="diary-panel" aria-label="Shinobu 日记">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Daily diary</span>
          <h2>Shinobu 日记</h2>
          <p>回顾 Shinobu 每日记录的心情与思考。日记生成会遵守后端 memory/privacy 设置。</p>
        </div>
        <button
          type="button"
          className="settings-primary-button diary-generate-btn"
          onClick={handleGenerate}
          disabled={generating}
        >
          <Sparkles size={16} />
          {generating ? '正在生成...' : '生成今日日记'}
        </button>
        <button
          type="button"
          className="settings-secondary-button diary-export-btn"
          onClick={() => handleExport()}
        >
          导出 Markdown
        </button>
      </header>

      {error ? <p className="settings-status-error" aria-live="polite">{error}</p> : null}

      {state === 'loading' ? (
        <div className="settings-skeleton"><span /><span /><span /></div>
      ) : null}

      {state === 'error' ? (
        <div className="diary-empty">
          <BookOpen size={40} />
          <h3>日记加载失败</h3>
          <p>{error || '请稍后重试。'}</p>
          <button type="button" className="settings-secondary-button" onClick={loadDiaries}>
            <RefreshCw size={14} /> 重新加载
          </button>
        </div>
      ) : null}

      {state === 'empty' ? (
        <div className="diary-empty">
          <BookOpen size={40} />
          <h3>还没有日记</h3>
          <p>让 Shinobu 为你生成今日回顾吧。</p>
          <button
            type="button"
            className="settings-primary-button"
            onClick={handleGenerate}
            disabled={generating}
          >
            <Sparkles size={16} />
            {generating ? '正在生成...' : '生成今日日记'}
          </button>
        </div>
      ) : null}

      {state === 'ready' ? (
        <>
          {/* Calendar */}
          <div className="diary-calendar">
            <div className="diary-calendar-header">
              <button type="button" onClick={handlePrevMonth} aria-label="上个月">
                <ChevronLeft size={18} />
              </button>
              <strong>{monthLabel}</strong>
              <button type="button" onClick={handleNextMonth} aria-label="下个月">
                <ChevronRight size={18} />
              </button>
            </div>
            <div className="diary-calendar-grid">
              {DAY_NAMES.map(name => (
                <div className="diary-weekday" key={name}>{name}</div>
              ))}
              {monthDays.map(d => {
                const has = diaryDates.has(d.date);
                const isToday = d.date === today;
                const isSelected = d.date === selectedDate;
                let cls = 'diary-day';
                if (has) cls += ' has-entry';
                if (isToday) cls += ' is-today';
                if (isSelected) cls += ' is-selected';
                if (!d.isCurrentMonth) cls += ' is-other-month';
                return (
                  <button
                    key={d.date}
                    type="button"
                    className={cls}
                    onClick={() => handleSelectDate(d.date)}
                    disabled={!d.isCurrentMonth}
                    aria-label={d.date}
                  >
                    <span className="diary-day-number">{d.day}</span>
                    {has ? <span className="diary-day-dot" /> : null}
                  </button>
                );
              })}
            </div>
          </div>

          {/* List */}
          <div className="diary-list">
            {sortedDiaries.map(item => (
              <button
                key={item.diary_id}
                type="button"
                className={`diary-item${selectedDate === item.date ? ' is-selected' : ''}`}
                onClick={() => handleSelectDiaryItem(item)}
              >
                <div className="diary-item-header">
                  <span className="diary-item-date">
                    <Calendar size={14} />
                    {formatDateChinese(item.date)}
                  </span>
                  {item.mood ? (
                    <span className="diary-mood">{MOOD_EMOJI[item.mood] || '\u{1F4AD}'} {item.mood}</span>
                  ) : null}
                </div>
                <strong className="diary-item-title">{item.title}</strong>
                <p className="diary-item-summary">{item.summary}</p>
              </button>
            ))}
          </div>
        </>
      ) : null}

      {/* Detail section */}
      {selectedDate && state === 'ready' ? (
        <div className="diary-detail" role="region" aria-label="日记详情">
          <div className="diary-detail-header">
            <h3>
              {detailLoading ? '加载中...' : detail ? detail.title : `${formatDateChinese(selectedDate)} 没有日记记录`}
            </h3>
            <button
              type="button"
              className="diary-detail-close"
              onClick={closeDetail}
              aria-label="关闭详情"
            >
              <X size={16} />
            </button>
          </div>

          {detailLoading ? (
            <div className="settings-skeleton"><span /></div>
          ) : detailError ? (
            <p className="settings-status-error">{detailError}</p>
          ) : detail ? (
            <>
              <div className="diary-detail-meta">
                <span><Calendar size={14} /> {formatDateChinese(detail.date)}</span>
                {detail.mood ? (
                  <span className="diary-mood">{MOOD_EMOJI[detail.mood] || '\u{1F4AD}'} {detail.mood}</span>
                ) : null}
                {detail.tags.length ? (
                  <ul className="diary-tags" aria-label="日记标签">
                    {detail.tags.map(tag => <li key={tag}>{tag}</li>)}
                  </ul>
                ) : null}
              </div>
              <div className="diary-detail-content">
                {detail.content.split('\n').map((line, i) => (
                  <p key={i}>{line || ' '}</p>
                ))}
              </div>
              <p className="diary-detail-note">这是 Shinobu 视角的当日回顾。</p>
              <button
                type="button"
                className="settings-secondary-button"
                onClick={handleForceRegenerate}
                disabled={generating}
                style={{ marginTop: 12 }}
              >
                <RefreshCw size={14} />
                {generating ? '重新生成中...' : '重新生成'}
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      {/* Privacy notice */}
      {state !== 'loading' ? (
        <p className="diary-privacy-note">日记生成会遵守后端 memory/privacy 设置。</p>
      ) : null}
    </section>
  );
}
