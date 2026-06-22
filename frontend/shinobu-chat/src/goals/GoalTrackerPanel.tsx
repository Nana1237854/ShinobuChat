import { useEffect, useState } from 'react';
import { checkinGoal, createGoal, listGoals, updateGoal } from '../api/goals';
import type { GoalItem } from '../types';

type GoalTrackerPanelProps = {
  accessToken: string;
  onGoalsChanged?: () => void;
};

type GoalForm = {
  title: string;
  description: string;
  category: string;
  cadence_days: number;
};

const initialForm: GoalForm = {
  title: '',
  description: '',
  category: '',
  cadence_days: 7,
};

export function GoalTrackerPanel({ accessToken, onGoalsChanged }: GoalTrackerPanelProps) {
  const [goals, setGoals] = useState<GoalItem[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [form, setForm] = useState<GoalForm>(initialForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshGoals = async () => {
    setState('loading');
    setError(null);
    try {
      const result = await listGoals(accessToken, { include_completed: true });
      setGoals(result);
      setState(result.length ? 'ready' : 'empty');
    } catch (nextError) {
      setState('error');
      setError(nextError instanceof Error ? nextError.message : '无法加载长期目标');
    }
  };

  useEffect(() => {
    refreshGoals();
  }, [accessToken]);

  const handleCreateGoal = async () => {
    if (!form.title.trim()) {
      setError('请先填写目标标题。');
      return;
    }
    setBusyKey('create');
    setError(null);
    setNotice(null);
    try {
      await createGoal(accessToken, {
        title: form.title.trim(),
        description: form.description.trim() || null,
        category: form.category.trim() || null,
        cadence_days: form.cadence_days,
      });
      setForm(initialForm);
      await refreshGoals();
      onGoalsChanged?.();
      setNotice('长期目标已创建。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '创建目标失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleUpdateStatus = async (goal: GoalItem, status: GoalItem['status']) => {
    setBusyKey(`${status}:${goal.id}`);
    setError(null);
    setNotice(null);
    try {
      await updateGoal(accessToken, goal.id, { status });
      await refreshGoals();
      onGoalsChanged?.();
      setNotice(`已将“${goal.title}”更新为${status === 'paused' ? '暂停' : status === 'completed' ? '完成' : '进行中'}。`);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '更新目标状态失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleSaveEdit = async (goal: GoalItem) => {
    setBusyKey(`save:${goal.id}`);
    setError(null);
    setNotice(null);
    try {
      await updateGoal(accessToken, goal.id, {
        title: goal.title,
        description: goal.description || null,
        cadence_days: goal.cadence_days,
        category: goal.category || null,
      });
      setEditingId(null);
      await refreshGoals();
      onGoalsChanged?.();
      setNotice('目标内容已更新。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '保存目标失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleCheckin = async (goal: GoalItem) => {
    setBusyKey(`checkin:${goal.id}`);
    setError(null);
    setNotice(null);
    try {
      const result = await checkinGoal(accessToken, goal.id);
      await refreshGoals();
      onGoalsChanged?.();
      setNotice(result.message || `已为“${goal.title}”记录一次进度。`);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '记录进度失败');
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <section className="goal-panel" aria-label="长期目标">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Long-term goals</span>
          <h2>长期目标</h2>
          <p>这里更偏陪伴式追踪，不做高压打卡。当前后端的 check-in 接口还不接收进展文本，后续如需自由填写需要后端配合。</p>
        </div>
      </header>

      <div className="goal-create-card">
        <h3>创建一个新目标</h3>
        <div className="goal-form-grid">
          <input type="text" placeholder="标题（必填）" value={form.title} onChange={event => setForm(current => ({ ...current, title: event.target.value }))} />
          <input type="text" placeholder="类别（可选）" value={form.category} onChange={event => setForm(current => ({ ...current, category: event.target.value }))} />
          <textarea placeholder="描述（可选）" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} rows={3} />
          <label>
            <span>追踪频率（天）</span>
            <input type="number" min="1" max="365" value={form.cadence_days} onChange={event => setForm(current => ({ ...current, cadence_days: Number(event.target.value) || 7 }))} />
          </label>
        </div>
        <div className="goal-create-actions">
          <button type="button" className="settings-primary-button" onClick={handleCreateGoal} disabled={busyKey === 'create'}>
            {busyKey === 'create' ? '创建中' : '创建目标'}
          </button>
        </div>
      </div>

      {error ? <p className="settings-status-error">{error}</p> : null}
      {notice ? <p className="settings-notice">{notice}</p> : null}

      {state === 'loading' ? <div className="settings-skeleton"><span /><span /><span /></div> : null}
      {state === 'empty' ? <div className="settings-empty-state"><h3>还没有长期目标</h3><p>从上面的表单开始，先记录一件你想持续推进的事。</p></div> : null}
      {state === 'error' ? <div className="settings-empty-state"><h3>目标列表暂时不可用</h3><p>{error || '请稍后重试。'}</p><button type="button" className="settings-secondary-button" onClick={refreshGoals}>重新加载</button></div> : null}

      {state === 'ready' ? (
        <div className="goal-list">
          {goals.map(goal => (
            <article className="goal-card" key={goal.id}>
              <div className="goal-card-top">
                <div>
                  {editingId === goal.id ? (
                    <input type="text" value={goal.title} onChange={event => setGoals(current => current.map(item => item.id === goal.id ? { ...item, title: event.target.value } : item))} />
                  ) : (
                    <h3>{goal.title}</h3>
                  )}
                  <p>{goal.category || '未分类'} · {goal.status}</p>
                </div>
                <span className={`goal-status-chip goal-status-${goal.status}`}>{goal.status}</span>
              </div>
              {editingId === goal.id ? (
                <>
                  <textarea rows={3} value={goal.description || ''} onChange={event => setGoals(current => current.map(item => item.id === goal.id ? { ...item, description: event.target.value } : item))} />
                  <label>
                    <span>追踪频率（天）</span>
                    <input type="number" min="1" max="365" value={goal.cadence_days} onChange={event => setGoals(current => current.map(item => item.id === goal.id ? { ...item, cadence_days: Number(event.target.value) || item.cadence_days } : item))} />
                  </label>
                </>
              ) : (
                <p className="goal-description">{goal.description || '这个目标暂时还没有补充描述。'}</p>
              )}
              <div className="goal-meta">
                <span>下次检查：{goal.next_check_at ? new Date(goal.next_check_at).toLocaleString('zh-CN') : '未安排'}</span>
                <span>上次记录：{goal.last_checked_at ? new Date(goal.last_checked_at).toLocaleString('zh-CN') : '还没有'}</span>
              </div>
              <div className="goal-actions">
                {editingId === goal.id ? (
                  <button type="button" className="settings-primary-button" onClick={() => handleSaveEdit(goal)} disabled={busyKey === `save:${goal.id}`}>
                    {busyKey === `save:${goal.id}` ? '保存中' : '保存编辑'}
                  </button>
                ) : (
                  <button type="button" className="settings-secondary-button" onClick={() => setEditingId(goal.id)}>
                    编辑
                  </button>
                )}
                {goal.status !== 'paused' ? <button type="button" className="settings-secondary-button" onClick={() => handleUpdateStatus(goal, 'paused')} disabled={busyKey === `paused:${goal.id}`}>暂停</button> : null}
                {goal.status === 'paused' ? <button type="button" className="settings-secondary-button" onClick={() => handleUpdateStatus(goal, 'active')} disabled={busyKey === `active:${goal.id}`}>恢复</button> : null}
                {goal.status !== 'completed' ? <button type="button" className="settings-secondary-button" onClick={() => handleUpdateStatus(goal, 'completed')} disabled={busyKey === `completed:${goal.id}`}>完成</button> : null}
                {goal.status === 'active' ? <button type="button" className="settings-primary-button" onClick={() => handleCheckin(goal)} disabled={busyKey === `checkin:${goal.id}`}>{busyKey === `checkin:${goal.id}` ? '记录中' : '记录进度'}</button> : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
