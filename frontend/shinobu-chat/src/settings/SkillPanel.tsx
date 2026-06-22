import { useEffect, useState } from 'react';
import { Download, FileCode2, Pencil, Plus, Save, Store, Trash2, X } from 'lucide-react';
import {
  deleteUserSkill,
  getUserSkill,
  installMarketSkill,
  installUserSkill,
  listMarketSkills,
  listUserSkills,
  setUserSkillEnabled,
  updateUserSkill,
} from '../api/client';
import type { MarketSkill, UserSkill } from '../types';

type SkillPanelProps = {
  accessToken: string;
};

const starterSkill = `---
name: my-skill
description: 用一句话说明这个 Skill 解决什么问题
keywords: [触发词]
---

# My Skill

## 触发条件

说明什么时候应使用这个 Skill。

## 工作流程

1. 第一步
2. 第二步

## 输出格式

说明结果如何呈现。
`;

export function SkillPanel({ accessToken }: SkillPanelProps) {
  const [tab, setTab] = useState<'mine' | 'market'>('mine');
  const [skills, setSkills] = useState<UserSkill[]>([]);
  const [marketSkills, setMarketSkills] = useState<MarketSkill[]>([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [content, setContent] = useState(starterSkill);
  const [busy, setBusy] = useState<string | null>('loading');
  const [marketBusy, setMarketBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadMySkills = async () => {
    setBusy('loading');
    try {
      setSkills(await listUserSkills(accessToken));
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法加载 Skill');
    } finally {
      setBusy(null);
    }
  };

  const loadMarket = async () => {
    setMarketBusy('loading');
    try {
      setMarketSkills(await listMarketSkills());
      setMessage(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法加载市场');
    } finally {
      setMarketBusy(null);
    }
  };

  useEffect(() => {
    loadMySkills();
  }, [accessToken]);

  const switchTab = (next: 'mine' | 'market') => {
    setTab(next);
    setEditorOpen(false);
    setMessage(null);
    if (next === 'market' && marketSkills.length === 0) loadMarket();
  };

  const openInstall = () => {
    setEditingId(null);
    setContent(starterSkill);
    setEditorOpen(true);
    setMessage(null);
  };

  const openEdit = async (skill: UserSkill) => {
    setBusy(skill.id);
    setMessage(null);
    try {
      const detail = await getUserSkill(accessToken, skill.id);
      setEditingId(skill.id);
      setContent(detail.content || starterSkill);
      setEditorOpen(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '无法读取 Skill');
    } finally {
      setBusy(null);
    }
  };

  const saveSkill = async () => {
    const wasEditing = Boolean(editingId);
    setBusy('saving');
    setMessage(null);
    try {
      if (editingId) await updateUserSkill(accessToken, editingId, content);
      else await installUserSkill(accessToken, content);
      setEditorOpen(false);
      setEditingId(null);
      await loadMySkills();
      setMessage(wasEditing ? 'Skill 已更新。' : 'Skill 已安装。');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '保存 Skill 失败');
      setBusy(null);
    }
  };

  const toggleSkill = async (skill: UserSkill) => {
    setBusy(skill.id);
    setMessage(null);
    try {
      const updated = await setUserSkillEnabled(accessToken, skill.id, !skill.enabled);
      setSkills(current => current.map(item => item.id === skill.id ? updated : item));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '更新 Skill 状态失败');
    } finally {
      setBusy(null);
    }
  };

  const removeSkill = async (skill: UserSkill) => {
    if (!window.confirm(`删除 Skill"${skill.name}"？此操作无法撤销。`)) return;
    setBusy(skill.id);
    setMessage(null);
    try {
      await deleteUserSkill(accessToken, skill.id);
      setSkills(current => current.filter(item => item.id !== skill.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '删除 Skill 失败');
    } finally {
      setBusy(null);
    }
  };

  const doMarketInstall = async (name: string) => {
    setMarketBusy(name);
    setMessage(null);
    try {
      await installMarketSkill(accessToken, name);
      setMessage(`"${name}" 已从市场安装。`);
      await loadMySkills();
      await loadMarket();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '安装失败');
    } finally {
      setMarketBusy(null);
    }
  };

  return (
    <section className="skill-panel" aria-label="Skill 管理">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">SKILL.md library</span>
          <h2>技能管理</h2>
          <p>目录只向模型提供名称与描述；完整 Markdown 仅在匹配或明确激活时加载。</p>
        </div>
        <div className="skill-tab-toggles">
          <button
            type="button"
            className={tab === 'mine' ? 'settings-tab is-active' : 'settings-tab'}
            onClick={() => switchTab('mine')}
          >
            <FileCode2 size={15} />我的 Skill
          </button>
          <button
            type="button"
            className={tab === 'market' ? 'settings-tab is-active' : 'settings-tab'}
            onClick={() => switchTab('market')}
          >
            <Store size={15} />市场
          </button>
        </div>
      </header>

      {message ? <p className="settings-notice" aria-live="polite">{message}</p> : null}

      {/* ---- My Skills Tab ---- */}
      {tab === 'mine' ? (
        <>
          <div style={{ marginBottom: 12 }}>
            <button type="button" className="settings-primary-button" onClick={openInstall}>
              <Plus size={16} />安装 Skill
            </button>
          </div>

          {busy === 'loading' && skills.length === 0 ? (
            <div className="settings-skeleton"><span /><span /><span /></div>
          ) : null}

          {busy !== 'loading' && skills.length === 0 ? (
            <div className="settings-empty-state">
              <FileCode2 size={30} />
              <h3>还没有用户 Skill</h3>
              <p>从一份带 YAML frontmatter 的纯 SKILL.md 开始。name 与 description 必填。</p>
              <button type="button" className="settings-secondary-button" onClick={openInstall}>
                创建第一份 Skill
              </button>
            </div>
          ) : null}

          <div className="skill-list">
            {skills.map(skill => (
              <article className={skill.enabled ? 'skill-row' : 'skill-row is-disabled'} key={skill.id}>
                <div className="skill-icon"><FileCode2 size={18} /></div>
                <div className="skill-copy">
                  <div>
                    <h3>{skill.name}</h3>
                    <span>{skill.installed_from === 'text' ? 'SKILL.md' : skill.installed_from}</span>
                  </div>
                  <p>{skill.description}</p>
                  {skill.keywords.length ? (
                    <ul aria-label="触发词">
                      {skill.keywords.map(keyword => <li key={keyword}>{keyword}</li>)}
                    </ul>
                  ) : null}
                </div>
                <div className="skill-actions">
                  <button
                    type="button"
                    role="switch"
                    aria-label={`${skill.name} ${skill.enabled ? '已启用' : '已停用'}`}
                    aria-checked={skill.enabled}
                    className={skill.enabled ? 'settings-toggle is-on' : 'settings-toggle'}
                    onClick={() => toggleSkill(skill)}
                    disabled={busy === skill.id}
                  >
                    <span />
                  </button>
                  <button type="button" title="编辑 Skill" onClick={() => openEdit(skill)} disabled={busy === skill.id}>
                    <Pencil size={16} />
                  </button>
                  <button type="button" title="删除 Skill" onClick={() => removeSkill(skill)} disabled={busy === skill.id}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </article>
            ))}
          </div>

          {editorOpen ? (
            <div className="skill-editor-backdrop" role="presentation">
              <section className="skill-editor" role="dialog" aria-modal="true" aria-label={editingId ? '编辑 Skill' : '安装 Skill'}>
                <header>
                  <div>
                    <span className="settings-eyebrow">{editingId ? 'Edit' : 'Install'}</span>
                    <h3>{editingId ? '编辑 SKILL.md' : '安装纯 SKILL.md'}</h3>
                  </div>
                  <button type="button" title="关闭编辑器" onClick={() => setEditorOpen(false)}><X size={17} /></button>
                </header>
                <p>frontmatter 中必须包含小写唯一 name 和非空 description。正文会原样保存。</p>
                <textarea
                  value={content}
                  onChange={event => setContent(event.target.value)}
                  spellCheck={false}
                  aria-label="SKILL.md 内容"
                />
                <footer>
                  <button type="button" className="settings-secondary-button" onClick={() => setEditorOpen(false)}>
                    取消
                  </button>
                  <button type="button" className="settings-primary-button" onClick={saveSkill} disabled={busy === 'saving'}>
                    <Save size={15} />{busy === 'saving' ? '保存中' : '保存 Skill'}
                  </button>
                </footer>
              </section>
            </div>
          ) : null}
        </>
      ) : null}

      {/* ---- Market Tab ---- */}
      {tab === 'market' ? (
        <>
          {marketBusy === 'loading' ? (
            <div className="settings-skeleton"><span /><span /><span /></div>
          ) : null}

          {marketBusy !== 'loading' && marketSkills.length === 0 ? (
            <div className="settings-empty-state">
              <Store size={30} />
              <h3>市场暂未上线</h3>
              <p>官方推荐 Skill 即将发布，敬请期待。</p>
            </div>
          ) : null}

          <div className="skill-list">
            {marketSkills.map(item => {
              const alreadyInstalled = skills.some(s => s.name === item.name);
              return (
                <article className={alreadyInstalled ? 'skill-row is-disabled' : 'skill-row'} key={item.name}>
                  <div className="skill-icon"><Store size={18} /></div>
                  <div className="skill-copy">
                    <div>
                      <h3>{item.name}</h3>
                      <span>v{item.version} by {item.author}</span>
                      {item.official ? <span className="skill-badge-official">官方</span> : null}
                    </div>
                    <p>{item.description}</p>
                    {item.tags.length ? (
                      <ul aria-label="标签">
                        {item.tags.map(tag => <li key={tag}>{tag}</li>)}
                      </ul>
                    ) : null}
                  </div>
                  <div className="skill-actions">
                    {alreadyInstalled ? (
                      <span className="skill-installed-hint">已安装</span>
                    ) : (
                      <button
                        type="button"
                        className="settings-primary-button"
                        onClick={() => doMarketInstall(item.name)}
                        disabled={marketBusy === item.name}
                      >
                        <Download size={14} />
                        {marketBusy === item.name ? '安装中' : '安装'}
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </>
      ) : null}
    </section>
  );
}
