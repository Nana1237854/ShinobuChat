import { useEffect, useState } from 'react';
import { Download, FileCode2, Pencil, Plus, Save, Store, Trash2, Upload, X } from 'lucide-react';
import {
  deleteSkill,
  getSkillDetail,
  installMarketSkill,
  installSkillFromText,
  listSkillMarket,
  listUserSkills,
  toggleSkill,
  updateSkill,
} from '../api/skills';
import type { MarketSkill, SkillSummary } from '../types';

type SkillPanelProps = {
  accessToken: string;
};

type LibraryTab = 'mine' | 'market';
type InstallTab = 'markdown' | 'github' | 'upload';

type SkillDetailDraft = {
  id: string;
  name: string;
  content: string;
};

const starterSkill = `---
name: example-skill
description: 一句话描述这个 Skill 解决什么问题
keywords: [示例]
version: 1.0.0
---

# Example Skill

## Trigger

说明什么情况下应该使用这个 Skill。

## Workflow

1. 第一步
2. 第二步

## Output

说明结果如何呈现。
`;

export function SkillPanel({ accessToken }: SkillPanelProps) {
  const [libraryTab, setLibraryTab] = useState<LibraryTab>('mine');
  const [installTab, setInstallTab] = useState<InstallTab>('markdown');
  const [skills, setSkills] = useState<SkillSummary[]>([]);
  const [marketSkills, setMarketSkills] = useState<MarketSkill[]>([]);
  const [editorDraft, setEditorDraft] = useState<SkillDetailDraft | null>(null);
  const [markdownContent, setMarkdownContent] = useState(starterSkill);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [marketState, setMarketState] = useState<'idle' | 'loading' | 'ready' | 'empty' | 'error'>('idle');
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshSkills = async () => {
    setLoadState('loading');
    setError(null);
    try {
      const result = await listUserSkills(accessToken);
      setSkills(result);
      setLoadState(result.length ? 'ready' : 'empty');
    } catch (nextError) {
      setLoadState('error');
      setError(nextError instanceof Error ? nextError.message : '无法加载 Skill 列表');
    }
  };

  const refreshMarket = async () => {
    setMarketState('loading');
    setError(null);
    try {
      const result = await listSkillMarket();
      setMarketSkills(result);
      setMarketState(result.length ? 'ready' : 'empty');
    } catch (nextError) {
      setMarketState('error');
      setError(nextError instanceof Error ? nextError.message : '无法加载 Skill 市场');
    }
  };

  useEffect(() => {
    refreshSkills();
  }, [accessToken]);

  const openEditor = async (skillId: string) => {
    setBusyKey(`load:${skillId}`);
    setError(null);
    setNotice(null);
    try {
      const detail = await getSkillDetail(accessToken, skillId);
      setEditorDraft({
        id: detail.id,
        name: detail.name,
        content: detail.content,
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '无法读取 Skill 详情');
    } finally {
      setBusyKey(null);
    }
  };

  const handleInstallMarkdown = async () => {
    if (!markdownContent.trim()) {
      setError('请先输入完整的 SKILL.md 内容。');
      return;
    }

    setBusyKey('install');
    setError(null);
    setNotice(null);
    try {
      await installSkillFromText(accessToken, markdownContent);
      await refreshSkills();
      setNotice('Skill 已安装，可继续编辑或启停。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '安装 Skill 失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleToggleSkill = async (skill: SkillSummary) => {
    const previous = skills;
    const nextEnabled = !skill.enabled;
    setSkills(current => current.map(item => item.id === skill.id ? { ...item, enabled: nextEnabled } : item));
    setBusyKey(`toggle:${skill.id}`);
    setError(null);
    setNotice(null);
    try {
      const updated = await toggleSkill(accessToken, skill.id, nextEnabled);
      setSkills(current => current.map(item => item.id === skill.id ? updated : item));
      setNotice(nextEnabled ? `已启用 ${skill.name}` : `已停用 ${skill.name}`);
    } catch (nextError) {
      setSkills(previous);
      setError(nextError instanceof Error ? nextError.message : '更新 Skill 状态失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleDeleteSkill = async (skill: SkillSummary) => {
    const confirmed = window.confirm(`确认删除 Skill “${skill.name}”吗？此操作无法撤销。`);
    if (!confirmed) return;

    setBusyKey(`delete:${skill.id}`);
    setError(null);
    setNotice(null);
    try {
      await deleteSkill(accessToken, skill.id);
      setSkills(current => current.filter(item => item.id !== skill.id));
      setNotice(`已删除 ${skill.name}`);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '删除 Skill 失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleSaveEditor = async () => {
    if (!editorDraft) return;

    setBusyKey(`save:${editorDraft.id}`);
    setError(null);
    setNotice(null);
    try {
      await updateSkill(accessToken, editorDraft.id, editorDraft.content);
      await refreshSkills();
      setEditorDraft(null);
      setNotice('Skill 内容已更新。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '保存 Skill 失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleInstallMarketSkill = async (item: MarketSkill) => {
    setBusyKey(`market:${item.name}`);
    setError(null);
    setNotice(null);
    try {
      await installMarketSkill(accessToken, item.name);
      await refreshSkills();
      await refreshMarket();
      setNotice(`已从市场安装 ${item.name}`);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '市场 Skill 安装失败');
    } finally {
      setBusyKey(null);
    }
  };

  const openMarket = async () => {
    setLibraryTab('market');
    if (marketState === 'idle') {
      await refreshMarket();
    }
  };

  return (
    <section className="skill-panel" aria-label="技能管理">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">SKILL.md library</span>
          <h2>技能管理</h2>
          <p>用户 Skill 仅作为说明文档存储，不在前端执行任意代码。安装、编辑、删除和启停都走真实接口。</p>
        </div>
        <div className="skill-tab-toggles">
          <button
            type="button"
            className={libraryTab === 'mine' ? 'settings-tab is-active' : 'settings-tab'}
            onClick={() => setLibraryTab('mine')}
          >
            <FileCode2 size={15} />我的 Skill
          </button>
          <button
            type="button"
            className={libraryTab === 'market' ? 'settings-tab is-active' : 'settings-tab'}
            onClick={openMarket}
          >
            <Store size={15} />官方市场
          </button>
        </div>
      </header>

      {error ? <p className="settings-status-error" aria-live="polite">{error}</p> : null}
      {notice ? <p className="settings-notice" aria-live="polite">{notice}</p> : null}

      {libraryTab === 'mine' ? (
        <>
          <div className="skill-install-panel">
            <div className="skill-install-tabs" role="tablist" aria-label="安装方式">
              <button
                type="button"
                className={installTab === 'markdown' ? 'settings-tab is-active' : 'settings-tab'}
                onClick={() => setInstallTab('markdown')}
              >
                <FileCode2 size={15} />手写 Markdown
              </button>
              <button
                type="button"
                className={installTab === 'github' ? 'settings-tab is-active' : 'settings-tab'}
                onClick={() => setInstallTab('github')}
              >
                <Download size={15} />GitHub URL
              </button>
              <button
                type="button"
                className={installTab === 'upload' ? 'settings-tab is-active' : 'settings-tab'}
                onClick={() => setInstallTab('upload')}
              >
                <Upload size={15} />上传文件
              </button>
            </div>

            {installTab === 'markdown' ? (
              <div className="skill-install-card">
                <div className="skill-install-copy">
                  <h3>安装新 Skill</h3>
                  <p>先完成最可靠的手写 `SKILL.md` 安装流。后端负责 frontmatter 校验，前端只负责安全传输和错误展示。</p>
                </div>
                <textarea
                  value={markdownContent}
                  onChange={event => setMarkdownContent(event.target.value)}
                  spellCheck={false}
                  aria-label="SKILL.md 安装内容"
                />
                <div className="skill-install-actions">
                  <button type="button" className="settings-secondary-button" onClick={() => setMarkdownContent(starterSkill)}>
                    恢复模板
                  </button>
                  <button
                    type="button"
                    className="settings-primary-button"
                    onClick={handleInstallMarkdown}
                    disabled={busyKey === 'install'}
                  >
                    <Plus size={15} />{busyKey === 'install' ? '安装中' : '安装 Skill'}
                  </button>
                </div>
              </div>
            ) : null}

            {installTab === 'github' ? (
              <div className="skill-install-placeholder">
                <h3>GitHub URL 安装即将支持</h3>
                <p>当前前端保留了入口，但后端尚未提供对应安装流。需要后端配合后再打开真实提交。</p>
              </div>
            ) : null}

            {installTab === 'upload' ? (
              <div className="skill-install-placeholder">
                <h3>上传 `.md` 文件即将支持</h3>
                <p>当前阶段不做假上传逻辑。后端开放文件导入接口后，这里再接真实能力。</p>
              </div>
            ) : null}
          </div>

          {loadState === 'loading' ? (
            <div className="settings-skeleton"><span /><span /><span /></div>
          ) : null}

          {loadState === 'empty' ? (
            <div className="settings-empty-state">
              <FileCode2 size={30} />
              <h3>还没有用户 Skill</h3>
              <p>你可以直接从上面的 Markdown 模板开始安装。frontmatter 至少需要 `name` 和 `description`。</p>
            </div>
          ) : null}

          {loadState === 'error' ? (
            <div className="settings-empty-state">
              <h3>Skill 列表暂时不可用</h3>
              <p>{error || '请稍后重试。'}</p>
              <button type="button" className="settings-secondary-button" onClick={refreshSkills}>重新加载</button>
            </div>
          ) : null}

          {loadState === 'ready' ? (
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
                      <ul aria-label="关键词">
                        {skill.keywords.map(keyword => <li key={keyword}>{keyword}</li>)}
                      </ul>
                    ) : null}
                  </div>
                  <div className="skill-actions">
                    <button
                      type="button"
                      role="switch"
                      aria-label={`${skill.name}${skill.enabled ? ' 已启用' : ' 已停用'}`}
                      aria-checked={skill.enabled}
                      className={skill.enabled ? 'settings-toggle is-on' : 'settings-toggle'}
                      onClick={() => handleToggleSkill(skill)}
                      disabled={busyKey === `toggle:${skill.id}`}
                    >
                      <span />
                    </button>
                    <button
                      type="button"
                      title="编辑 Skill"
                      onClick={() => openEditor(skill.id)}
                      disabled={busyKey === `load:${skill.id}`}
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      type="button"
                      title="删除 Skill"
                      onClick={() => handleDeleteSkill(skill)}
                      disabled={busyKey === `delete:${skill.id}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      {libraryTab === 'market' ? (
        <>
          {marketState === 'loading' ? (
            <div className="settings-skeleton"><span /><span /><span /></div>
          ) : null}

          {marketState === 'empty' ? (
            <div className="settings-empty-state">
              <Store size={30} />
              <h3>市场暂时为空</h3>
              <p>接口已接通，但当前没有返回任何官方 Skill 列表。</p>
            </div>
          ) : null}

          {marketState === 'error' ? (
            <div className="settings-empty-state">
              <h3>官方市场暂时不可用</h3>
              <p>{error || '请稍后重试，或等待后端市场接口稳定。'}</p>
              <button type="button" className="settings-secondary-button" onClick={refreshMarket}>重新加载</button>
            </div>
          ) : null}

          {marketState === 'ready' ? (
            <div className="skill-list">
              {marketSkills.map(item => {
                const alreadyInstalled = skills.some(skill => skill.name === item.name);
                return (
                  <article className={alreadyInstalled ? 'skill-row is-disabled' : 'skill-row'} key={item.name}>
                    <div className="skill-icon"><Store size={18} /></div>
                    <div className="skill-copy">
                      <div>
                        <h3>{item.name}</h3>
                        <span>v{item.version} · {item.author}</span>
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
                          onClick={() => handleInstallMarketSkill(item)}
                          disabled={busyKey === `market:${item.name}`}
                        >
                          <Download size={14} />
                          {busyKey === `market:${item.name}` ? '安装中' : '安装'}
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </>
      ) : null}

      {editorDraft ? (
        <div className="skill-editor-backdrop" role="presentation">
          <section className="skill-editor" role="dialog" aria-modal="true" aria-label="编辑 Skill">
            <header>
              <div>
                <span className="settings-eyebrow">Edit Skill</span>
                <h3>{editorDraft.name}</h3>
              </div>
              <button type="button" title="关闭编辑器" onClick={() => setEditorDraft(null)}><X size={17} /></button>
            </header>
            <p>编辑的是完整 `SKILL.md` 内容。前端不会执行用户写入的任何脚本，只做纯文本保存。</p>
            <textarea
              value={editorDraft.content}
              onChange={event => setEditorDraft(current => current ? { ...current, content: event.target.value } : current)}
              spellCheck={false}
              aria-label="Skill 编辑内容"
            />
            <footer>
              <button type="button" className="settings-secondary-button" onClick={() => setEditorDraft(null)}>
                取消
              </button>
              <button
                type="button"
                className="settings-primary-button"
                onClick={handleSaveEditor}
                disabled={busyKey === `save:${editorDraft.id}`}
              >
                <Save size={15} />{busyKey === `save:${editorDraft.id}` ? '保存中' : '保存 Skill'}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
