import { useEffect, useState } from 'react';
import {
  Check,
  Play,
  Plus,
  Star,
  Trash2,
  X,
  Pencil,
} from 'lucide-react';
import {
  createLocalApp,
  deleteLocalApp,
  listLocalApps,
  testLocalApp,
  updateLocalApp,
} from '../../api/localApps';
import {
  INTENT_TYPE_LABELS,
  type IntentType,
  type LocalApp,
  type LocalAppCreateParams,
} from '../../types';

type LocalAppsPanelProps = {
  accessToken: string;
};

const INTENT_TYPE_OPTIONS: IntentType[] = [
  'open_music',
  'open_browser',
  'open_ide',
  'open_file_explorer',
  'open_terminal',
  'open_note_app',
  'open_design_app',
  'open_chat_app',
  'open_custom',
];

const SCRIPT_EXTENSIONS = ['.bat', '.cmd', '.ps1'];

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function isScriptPath(path: string): boolean {
  const lower = path.toLowerCase();
  return SCRIPT_EXTENSIONS.some(ext => lower.endsWith(ext));
}

type EditorState = {
  mode: 'create' | 'edit';
  appId?: string;
  appKey: string;
  intentType: IntentType;
  displayName: string;
  executablePath: string;
  workingDir: string;
  args: string;
  keywords: string[];
  enabled: boolean;
  isDefaultForIntent: boolean;
  confirmRequired: boolean;
};

const emptyEditor = (): EditorState => ({
  mode: 'create',
  appKey: '',
  intentType: 'open_custom',
  displayName: '',
  executablePath: '',
  workingDir: '',
  args: '',
  keywords: [],
  enabled: true,
  isDefaultForIntent: false,
  confirmRequired: true,
});

export function LocalAppsPanel({ accessToken }: LocalAppsPanelProps) {
  const [apps, setApps] = useState<LocalApp[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [newKeyword, setNewKeyword] = useState('');
  const [testMessage, setTestMessage] = useState<string | null>(null);

  const refresh = async () => {
    setLoadState('loading');
    setError(null);
    try {
      const result = await listLocalApps(accessToken);
      setApps(result);
      setLoadState(result.length ? 'ready' : 'empty');
    } catch (e) {
      setLoadState('error');
      setError(e instanceof Error ? e.message : '无法加载本地应用列表');
    }
  };

  useEffect(() => {
    refresh();
  }, [accessToken]);

  const openCreate = () => {
    setEditor(emptyEditor());
    setNewKeyword('');
    setTestMessage(null);
  };

  const openEdit = (app: LocalApp) => {
    setEditor({
      mode: 'edit',
      appId: app.id,
      appKey: app.app_key,
      intentType: app.intent_type,
      displayName: app.display_name,
      executablePath: app.executable_path,
      workingDir: app.working_dir ?? '',
      args: app.args ?? '',
      keywords: app.keywords ?? [],
      enabled: app.enabled,
      isDefaultForIntent: app.is_default_for_intent,
      confirmRequired: app.confirm_required,
    });
    setNewKeyword('');
    setTestMessage(null);
  };

  const handleSave = async () => {
    if (!editor) return;
    if (!editor.appKey.trim()) {
      setError('app_key 不能为空');
      return;
    }
    if (!editor.displayName.trim()) {
      setError('显示名称不能为空');
      return;
    }
    if (!editor.executablePath.trim()) {
      setError('可执行文件路径不能为空');
      return;
    }

    const body: LocalAppCreateParams = {
      app_key: editor.appKey.trim(),
      intent_type: editor.intentType,
      display_name: editor.displayName.trim(),
      executable_path: editor.executablePath.trim(),
      working_dir: editor.workingDir.trim() || null,
      args: editor.args.trim() || null,
      keywords: editor.keywords,
      enabled: editor.enabled,
      is_default_for_intent: editor.isDefaultForIntent,
      confirm_required: editor.confirmRequired,
    };

    setBusyKey('save');
    setError(null);
    setNotice(null);
    try {
      if (editor.mode === 'create') {
        await createLocalApp(accessToken, body);
        setNotice('应用已添加');
      } else if (editor.appId) {
        await updateLocalApp(accessToken, editor.appId, body);
        setNotice('应用已更新');
      }
      setEditor(null);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleDelete = async (app: LocalApp) => {
    const confirmed = window.confirm(`确认删除应用 "${app.display_name}" 吗？此操作无法撤销。`);
    if (!confirmed) return;

    setBusyKey(`delete:${app.id}`);
    setError(null);
    setNotice(null);
    try {
      await deleteLocalApp(accessToken, app.id);
      setApps(current => current.filter(item => item.id !== app.id));
      setNotice(`已删除 ${app.display_name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleToggle = async (app: LocalApp) => {
    const previous = apps;
    const nextEnabled = !app.enabled;
    setApps(current =>
      current.map(item => (item.id === app.id ? { ...item, enabled: nextEnabled } : item)),
    );
    setBusyKey(`toggle:${app.id}`);
    setError(null);
    try {
      const updated = await updateLocalApp(accessToken, app.id, { enabled: nextEnabled });
      setApps(current =>
        current.map(item => (item.id === app.id ? updated : item)),
      );
      setNotice(nextEnabled ? `已启用 ${app.display_name}` : `已停用 ${app.display_name}`);
    } catch (e) {
      setApps(previous);
      setError(e instanceof Error ? e.message : '状态更新失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleSetDefault = async (app: LocalApp) => {
    if (app.is_default_for_intent) return;

    const previous = apps;
    setApps(current =>
      current.map(item => ({
        ...item,
        is_default_for_intent:
          item.intent_type === app.intent_type ? item.id === app.id : item.is_default_for_intent,
      })),
    );
    setBusyKey(`default:${app.id}`);
    setError(null);
    try {
      const updated = await updateLocalApp(accessToken, app.id, {
        is_default_for_intent: true,
      });
      setApps(current =>
        current.map(item => (item.id === app.id ? updated : item)),
      );
      setNotice(`已将 ${app.display_name} 设为 "${INTENT_TYPE_LABELS[app.intent_type]}" 的默认应用`);
    } catch (e) {
      setApps(previous);
      setError(e instanceof Error ? e.message : '设置默认失败');
    } finally {
      setBusyKey(null);
    }
  };

  const handleTest = async (app: LocalApp) => {
    setBusyKey(`test:${app.id}`);
    setTestMessage(null);
    setError(null);
    try {
      const result = await testLocalApp(accessToken, app.id);
      setTestMessage(result.success
        ? `测试通过: ${result.message}`
        : `测试失败: ${result.message}`);
      setNotice(`测试完成: ${app.display_name}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '测试启动失败');
    } finally {
      setBusyKey(null);
    }
  };

  const addKeyword = () => {
    const kw = newKeyword.trim();
    if (!kw || !editor) return;
    if (editor.keywords.includes(kw)) return;
    setEditor({ ...editor, keywords: [...editor.keywords, kw] });
    setNewKeyword('');
  };

  const removeKeyword = (kw: string) => {
    if (!editor) return;
    setEditor({ ...editor, keywords: editor.keywords.filter(k => k !== kw) });
  };

  return (
    <section className="local-apps-panel" aria-label="本地应用配置">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Local Agent Apps</span>
          <h2>本地应用</h2>
          <p>配置 Shinobu 可调用的本地应用。app_key 是自定义标识符，intent_type 决定触发场景。所有操作通过后端 API 执行，前端不直接运行 exe。</p>
        </div>
        <button type="button" className="settings-primary-button" onClick={openCreate}>
          <Plus size={15} />添加应用
        </button>
      </header>

      {error ? (
        <p className="settings-status-error" aria-live="polite">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="settings-notice" aria-live="polite">
          {notice}
        </p>
      ) : null}
      {testMessage ? (
        <p className="settings-notice" aria-live="polite">
          {testMessage}
        </p>
      ) : null}

      {loadState === 'loading' ? (
        <div className="settings-skeleton">
          <span />
          <span />
          <span />
        </div>
      ) : null}

      {loadState === 'empty' ? (
        <div className="settings-empty-state">
          <Play size={30} />
          <h3>还没有本地应用</h3>
          <p>点击「添加应用」配置 Shinobu 可以调用的本地程序。例如网易云音乐、VS Code 等。</p>
        </div>
      ) : null}

      {loadState === 'error' ? (
        <div className="settings-empty-state">
          <h3>加载失败</h3>
          <p>{error || '请稍后重试'}</p>
          <button type="button" className="settings-secondary-button" onClick={refresh}>
            重新加载
          </button>
        </div>
      ) : null}

      {loadState === 'ready' ? (
        <div className="local-apps-table">
          <div className="local-apps-table-header">
            <span className="col-key">标识符</span>
            <span className="col-intent">意图</span>
            <span className="col-name">名称</span>
            <span className="col-path">路径</span>
            <span className="col-status">状态</span>
            <span className="col-actions">操作</span>
          </div>
          {apps.map(app => (
            <article
              className={app.enabled ? 'local-app-row' : 'local-app-row is-disabled'}
              key={app.id}
            >
              <div className="col-key">
                <code>{app.app_key}</code>
                {app.is_default_for_intent ? (
                  <span className="local-app-default-badge" title="该意图的默认应用">
                    <Star size={11} />
                  </span>
                ) : null}
              </div>
              <div className="col-intent">
                <span className="intent-chip">{INTENT_TYPE_LABELS[app.intent_type]}</span>
              </div>
              <div className="col-name">{app.display_name}</div>
              <div className="col-path">
                <code className="path-text" title={app.executable_path}>
                  {app.executable_path}
                </code>
                {isScriptPath(app.executable_path) ? (
                  <span className="local-app-risk-badge" title="脚本文件存在风险">
                    高风险
                  </span>
                ) : null}
              </div>
              <div className="col-status">
                <button
                  type="button"
                  role="switch"
                  aria-label={`${app.display_name}${app.enabled ? ' 已启用' : ' 已停用'}`}
                  aria-checked={app.enabled}
                  className={app.enabled ? 'settings-toggle is-on' : 'settings-toggle'}
                  onClick={() => handleToggle(app)}
                  disabled={busyKey === `toggle:${app.id}`}
                >
                  <span />
                </button>
              </div>
              <div className="col-actions">
                <button
                  type="button"
                  title="编辑"
                  onClick={() => openEdit(app)}
                  disabled={!!busyKey}
                >
                  <Pencil size={15} />
                </button>
                <button
                  type="button"
                  title="设为默认"
                  onClick={() => handleSetDefault(app)}
                  disabled={app.is_default_for_intent || !!busyKey}
                >
                  <Star size={15} />
                </button>
                <button
                  type="button"
                  title="测试启动"
                  onClick={() => handleTest(app)}
                  disabled={busyKey === `test:${app.id}`}
                >
                  <Play size={15} />
                </button>
                <button
                  type="button"
                  title="删除"
                  onClick={() => handleDelete(app)}
                  disabled={busyKey === `delete:${app.id}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {editor ? (
        <div className="skill-editor-backdrop" role="presentation" onClick={() => setEditor(null)}>
          <section
            className="local-app-editor"
            role="dialog"
            aria-modal="true"
            aria-label={editor.mode === 'create' ? '添加本地应用' : '编辑本地应用'}
            onClick={e => e.stopPropagation()}
          >
            <header>
              <div>
                <span className="settings-eyebrow">
                  {editor.mode === 'create' ? 'New Local App' : 'Edit Local App'}
                </span>
                <h3>{editor.mode === 'create' ? '添加本地应用' : `编辑 ${editor.displayName || editor.appKey}`}</h3>
              </div>
              <button type="button" title="关闭" onClick={() => setEditor(null)}>
                <X size={17} />
              </button>
            </header>

            <div className="local-app-editor-body">
              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-app-key">app_key</label>
                  <p>自定义标识符，用于快捷触发。使用英文、数字和下划线。</p>
                </div>
                <div className="config-control">
                  <input
                    id="la-app-key"
                    type="text"
                    value={editor.appKey}
                    onChange={e => setEditor({ ...editor, appKey: e.target.value })}
                    placeholder="如 music, vscode"
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-intent-type">intent_type</label>
                  <p>意图类型，决定何时触发。选择「自定义」不会自动触发。</p>
                </div>
                <div className="config-control">
                  <select
                    id="la-intent-type"
                    value={editor.intentType}
                    onChange={e => setEditor({ ...editor, intentType: e.target.value as IntentType })}
                  >
                    {INTENT_TYPE_OPTIONS.map(option => (
                      <option key={option} value={option}>
                        {INTENT_TYPE_LABELS[option]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {editor.intentType === 'open_custom' ? (
                <p className="local-app-editor-hint">
                  自定义类型的应用不会自动触发，仅供手动调用。如需自动触发，请选择合适的 intent_type。
                </p>
              ) : null}

              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-display-name">display_name</label>
                  <p>在确认卡片和日志中显示的名称。</p>
                </div>
                <div className="config-control">
                  <input
                    id="la-display-name"
                    type="text"
                    value={editor.displayName}
                    onChange={e => setEditor({ ...editor, displayName: e.target.value })}
                    placeholder="如 网易云音乐"
                  />
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-exec-path">executable_path</label>
                  <p>请填写完整路径，如 D:\CloudMusic\cloudmusic.exe</p>
                </div>
                <div className="config-control">
                  <input
                    id="la-exec-path"
                    type="text"
                    value={editor.executablePath}
                    onChange={e => setEditor({ ...editor, executablePath: e.target.value })}
                    placeholder="D:\CloudMusic\cloudmusic.exe"
                    spellCheck={false}
                  />
                </div>
              </div>

              {editor.executablePath &&
                !editor.executablePath.toLowerCase().endsWith('.exe') &&
                !isScriptPath(editor.executablePath) ? (
                <p className="local-app-editor-hint">
                  提示：路径看起来不是 .exe 文件。如果是目录，请补充完整到 exe 文件。
                </p>
              ) : null}

              {isScriptPath(editor.executablePath) ? (
                <p className="local-app-editor-warning">
                  ⚠ 高风险警告：.bat/.cmd/.ps1 脚本可能会执行任意命令。请确保来源可信。
                </p>
              ) : null}

              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-working-dir">working_dir</label>
                  <p>工作目录，默认与可执行文件所在目录相同。</p>
                </div>
                <div className="config-control">
                  <input
                    id="la-working-dir"
                    type="text"
                    value={editor.workingDir}
                    onChange={e => setEditor({ ...editor, workingDir: e.target.value })}
                    placeholder="留空则使用 exe 所在目录"
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label htmlFor="la-args">args</label>
                  <p>启动参数，可选。</p>
                </div>
                <div className="config-control">
                  <input
                    id="la-args"
                    type="text"
                    value={editor.args}
                    onChange={e => setEditor({ ...editor, args: e.target.value })}
                    placeholder="如 --new-window"
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label>keywords</label>
                  <p>触发关键词，可选。按回车添加。</p>
                </div>
                <div className="config-control">
                  <div className="local-app-keywords-wrap">
                    <div className="local-app-keywords-input">
                      <input
                        type="text"
                        value={newKeyword}
                        onChange={e => setNewKeyword(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addKeyword();
                          }
                        }}
                        placeholder="输入关键词后按回车"
                        spellCheck={false}
                      />
                      <button
                        type="button"
                        className="settings-secondary-button"
                        onClick={addKeyword}
                        disabled={!newKeyword.trim()}
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                    {editor.keywords.length > 0 ? (
                      <ul className="local-app-keywords-list">
                        {editor.keywords.map(kw => (
                          <li key={kw}>
                            {kw}
                            <button
                              type="button"
                              className="keyword-remove-btn"
                              onClick={() => removeKeyword(kw)}
                              title="移除关键词"
                            >
                              <X size={12} />
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label>enabled</label>
                  <p>关闭后不会响应任何触发。</p>
                </div>
                <div className="config-control">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={editor.enabled}
                    className={editor.enabled ? 'settings-toggle is-on' : 'settings-toggle'}
                    onClick={() => setEditor({ ...editor, enabled: !editor.enabled })}
                  >
                    <span />
                  </button>
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label>is_default_for_intent</label>
                  <p>同 intent_type 只能有一个默认应用。设为默认后，同类型的其他应用会自动取消默认。</p>
                </div>
                <div className="config-control">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={editor.isDefaultForIntent}
                    className={
                      editor.isDefaultForIntent ? 'settings-toggle is-on' : 'settings-toggle'
                    }
                    onClick={() =>
                      setEditor({ ...editor, isDefaultForIntent: !editor.isDefaultForIntent })
                    }
                  >
                    <span />
                  </button>
                </div>
              </div>

              <div className="config-field">
                <div className="config-field-copy">
                  <label>confirm_required</label>
                  <p>开启后，打开应用前需要用户确认（单次确认）。建议保持开启。</p>
                </div>
                <div className="config-control">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={editor.confirmRequired}
                    className={
                      editor.confirmRequired ? 'settings-toggle is-on' : 'settings-toggle'
                    }
                    onClick={() =>
                      setEditor({ ...editor, confirmRequired: !editor.confirmRequired })
                    }
                  >
                    <span />
                  </button>
                </div>
              </div>
            </div>

            <footer className="local-app-editor-footer">
              <button
                type="button"
                className="settings-secondary-button"
                onClick={() => setEditor(null)}
              >
                取消
              </button>
              <button
                type="button"
                className="settings-primary-button"
                onClick={handleSave}
                disabled={busyKey === 'save'}
              >
                <Check size={15} />
                {busyKey === 'save' ? '保存中...' : editor.mode === 'create' ? '添加' : '保存'}
              </button>
            </footer>
          </section>
        </div>
      ) : null}
    </section>
  );
}
