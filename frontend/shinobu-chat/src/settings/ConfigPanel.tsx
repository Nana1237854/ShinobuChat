import { useEffect, useMemo, useState } from 'react';
import { Eye, EyeOff, RotateCcw, Save, ShieldCheck } from 'lucide-react';
import { getUserConfig, resetUserConfig, updateUserConfig } from '../api/config';
import type { ConfigField, ConfigUpdateRequest } from '../types';

type ConfigPanelProps = {
  accessToken: string;
};

type Scalar = string | number | boolean;

type FieldDefinition = {
  key: ConfigField['key'];
  label: string;
  description: string;
  kind: 'text' | 'secret' | 'number' | 'boolean' | 'select';
  min?: number;
  max?: number;
  step?: number;
  withSlider?: boolean;
  options?: Array<{ value: string; label: string }>;
};

type ConfigGroup = {
  title: string;
  description: string;
  fields: FieldDefinition[];
};

const SOURCE_LABELS: Record<ConfigField['source'], string> = {
  user: '用户覆盖',
  env: '环境变量',
  default: '默认值',
};

const groups: ConfigGroup[] = [
  {
    title: 'AI 通用',
    description: '控制主对话、超时和轻量调用限制。',
    fields: [
      { key: 'ai_api_key', label: 'AI API Key', description: '只显示脱敏预览，保存后会重新从服务端拉取。', kind: 'secret' },
      { key: 'ai_base_url', label: 'API Base URL', description: 'OpenAI 兼容接口地址。', kind: 'text' },
      { key: 'ai_model', label: '主对话模型', description: '聊天与工具编排使用的模型。', kind: 'text' },
      { key: 'ai_request_timeout_seconds', label: '请求超时（秒）', description: '单次请求允许的最长等待时间。', kind: 'number', min: 1, max: 600, step: 1 },
      { key: 'ai_supports_image_input', label: '支持图片输入', description: '标记当前模型是否接受视觉输入。', kind: 'boolean' },
      { key: 'ai_lightweight_max_tokens', label: '轻量调用最大 Tokens', description: '限制轻量推理场景的输出长度。', kind: 'number', min: 128, max: 131072, step: 128 },
    ],
  },
  {
    title: '角色扮演与决策',
    description: '区分对话表达和任务决策，避免所有能力共用同一组温度。',
    fields: [
      { key: 'roleplay_llm_model', label: '角色对话模型', description: 'Shinobu 的回复表达使用这一模型。', kind: 'text' },
      { key: 'roleplay_llm_temperature', label: '角色温度', description: '数值越高，表达变化越丰富。', kind: 'number', min: 0, max: 2, step: 0.1, withSlider: true },
      { key: 'decision_llm_model', label: '决策模型', description: '任务判断、工具选择与路由使用这一模型。', kind: 'text' },
      { key: 'decision_llm_temperature', label: '决策温度', description: '建议较低，保证任务路由稳定。', kind: 'number', min: 0, max: 2, step: 0.1, withSlider: true },
    ],
  },
  {
    title: '第三方服务',
    description: '搜索、语音合成和语音识别的外围连接。',
    fields: [
      { key: 'google_search_api_key', label: 'Google Search API Key', description: '供搜索聚合能力调用，始终以脱敏形式展示。', kind: 'secret' },
      { key: 'google_search_cx', label: 'Google Search CX', description: '自定义搜索引擎 ID。', kind: 'text' },
      { key: 'edge_tts_voice', label: 'Edge TTS Voice', description: '例如 `zh-CN-XiaoxiaoNeural`。', kind: 'text' },
      {
        key: 'asr_engine',
        label: '语音识别引擎',
        description: '按当前后端能力切换 Whisper 或 FunASR。',
        kind: 'select',
        options: [
          { value: 'whisper', label: 'Whisper' },
          { value: 'funasr', label: 'FunASR' },
        ],
      },
      { key: 'whisper_api_key', label: 'Whisper API Key', description: '仅保存新输入值，不会回显完整密钥。', kind: 'secret' },
    ],
  },
];

function fieldsToValues(fields: ConfigField[]): Record<string, Scalar> {
  return Object.fromEntries(fields.map(field => [field.key, field.value as Scalar]));
}

function maskPreview(value: string) {
  if (!value) return '未填写';
  if (value.length <= 8) return '••••••••';
  return `${value.slice(0, 4)}••••${value.slice(-4)}`;
}

function asNumber(value: Scalar, fallback = 0) {
  return typeof value === 'number' ? value : Number(value ?? fallback);
}

export function ConfigPanel({ accessToken }: ConfigPanelProps) {
  const [fields, setFields] = useState<ConfigField[]>([]);
  const [values, setValues] = useState<Record<string, Scalar>>({});
  const [initialValues, setInitialValues] = useState<Record<string, Scalar>>({});
  const [revealedSecrets, setRevealedSecrets] = useState<Record<string, boolean>>({});
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [actionState, setActionState] = useState<'idle' | 'saving' | 'resetting'>('idle');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoadState('loading');
    setError(null);
    try {
      const response = await getUserConfig(accessToken);
      const nextValues = fieldsToValues(response.fields);
      setFields(response.fields);
      setValues(nextValues);
      setInitialValues(nextValues);
      setRevealedSecrets({});
      setLoadState(response.fields.length ? 'ready' : 'empty');
    } catch (nextError) {
      setLoadState('error');
      setError(nextError instanceof Error ? nextError.message : '无法加载配置');
    }
  };

  useEffect(() => {
    refresh();
  }, [accessToken]);

  const fieldsByKey = useMemo(
    () => Object.fromEntries(fields.map(field => [field.key, field])) as Record<string, ConfigField>,
    [fields],
  );

  const dirtyKeys = useMemo(() => {
    return Object.keys(values).filter(key => values[key] !== initialValues[key]);
  }, [initialValues, values]);

  const dirtyPayload = useMemo(() => {
    const payload: ConfigUpdateRequest = {};
    for (const field of fields) {
      const currentValue = values[field.key];
      const initialValue = initialValues[field.key];
      if (currentValue === initialValue) continue;
      if (field.encrypted && currentValue === '') continue;
      payload[field.key as keyof ConfigUpdateRequest] = currentValue as never;
    }
    return payload;
  }, [fields, initialValues, values]);

  const updateValue = (key: string, value: Scalar) => {
    setValues(current => ({ ...current, [key]: value }));
  };

  const handleSecretFocus = (field: ConfigField) => {
    const current = values[field.key];
    const initial = initialValues[field.key];
    if (field.encrypted && current === initial) {
      updateValue(field.key, '');
    }
  };

  const handleSecretBlur = (field: ConfigField) => {
    if (!field.encrypted) return;
    const initial = initialValues[field.key];
    if (values[field.key] === '' && typeof initial === 'string' && initial.length > 0) {
      updateValue(field.key, initial);
    }
  };

  const handleSave = async () => {
    if (!Object.keys(dirtyPayload).length) return;
    setActionState('saving');
    setNotice(null);
    setError(null);
    try {
      await updateUserConfig(accessToken, dirtyPayload);
      await refresh();
      setNotice('配置已保存，界面已重新同步服务端状态。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '保存配置失败');
    } finally {
      setActionState('idle');
    }
  };

  const handleReset = async () => {
    const confirmed = window.confirm('确认将当前账户的模型配置重置为环境变量或默认值吗？');
    if (!confirmed) return;

    setActionState('resetting');
    setNotice(null);
    setError(null);
    try {
      await resetUserConfig(accessToken);
      await refresh();
      setNotice('已重置为环境变量或默认值。');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '重置配置失败');
    } finally {
      setActionState('idle');
    }
  };

  if (loadState === 'loading' && fields.length === 0) {
    return (
      <div className="settings-skeleton" aria-label="正在加载 AI 配置">
        <span />
        <span />
        <span />
      </div>
    );
  }

  if (loadState === 'error') {
    return (
      <section className="config-panel" aria-label="AI 模型配置错误状态">
        <header className="settings-content-header">
          <div>
            <span className="settings-eyebrow">Runtime configuration</span>
            <h2>模型与服务</h2>
            <p>配置接口暂时不可用，下面保留重试入口，不做假成功兜底。</p>
          </div>
          <span className="security-chip"><ShieldCheck size={15} />安全兜底</span>
        </header>
        <div className="settings-empty-state">
          <h3>暂时无法加载配置</h3>
          <p>{error || '请稍后重试，或检查后端配置接口是否可访问。'}</p>
          <button type="button" className="settings-secondary-button" onClick={refresh}>
            重新加载
          </button>
        </div>
      </section>
    );
  }

  if (loadState === 'empty') {
    return (
      <section className="config-panel" aria-label="AI 模型配置空状态">
        <header className="settings-content-header">
          <div>
            <span className="settings-eyebrow">Runtime configuration</span>
            <h2>模型与服务</h2>
            <p>接口已响应，但当前没有可展示的配置字段。</p>
          </div>
        </header>
        <div className="settings-empty-state">
          <h3>没有可编辑的配置项</h3>
          <p>这通常意味着后端尚未返回用户级字段列表，需要后端配合确认配置输出。</p>
        </div>
      </section>
    );
  }

  return (
    <section className="config-panel" aria-label="AI 模型与服务配置">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Runtime configuration</span>
          <h2>模型与服务</h2>
          <p>用户覆盖优先于环境变量。密钥字段只显示脱敏预览，保存成功后会重新从服务端拉取。</p>
        </div>
        <span className="security-chip"><ShieldCheck size={15} />密钥默认脱敏</span>
      </header>

      {error ? <p className="settings-status-error" aria-live="polite">{error}</p> : null}
      {notice ? <p className="settings-notice" aria-live="polite">{notice}</p> : null}

      <div className="config-groups">
        {groups.map(group => (
          <section className="config-group" key={group.title}>
            <header>
              <h3>{group.title}</h3>
              <p>{group.description}</p>
            </header>
            <div className="config-fields">
              {group.fields.map(definition => {
                const field = fieldsByKey[definition.key];
                const value = values[definition.key] ?? '';
                const source = field?.source ?? 'default';
                const dirty = value !== initialValues[definition.key];
                const secretPreview = typeof value === 'string' ? maskPreview(value) : '未填写';
                return (
                  <div className="config-field" key={definition.key} data-dirty={dirty || undefined}>
                    <div className="config-field-copy">
                      <label htmlFor={definition.key}>{definition.label}</label>
                      <p>{definition.description}</p>
                    </div>
                    <div className="config-control">
                      <span className={`source-badge source-${source}`}>{SOURCE_LABELS[source]}</span>

                      {definition.kind === 'boolean' ? (
                        <button
                          type="button"
                          role="switch"
                          aria-checked={Boolean(value)}
                          className={Boolean(value) ? 'settings-toggle is-on' : 'settings-toggle'}
                          onClick={() => updateValue(definition.key, !Boolean(value))}
                        >
                          <span />
                        </button>
                      ) : null}

                      {definition.kind === 'select' ? (
                        <select
                          id={definition.key}
                          value={String(value)}
                          onChange={event => updateValue(definition.key, event.target.value)}
                        >
                          {definition.options?.map(option => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                          ))}
                        </select>
                      ) : null}

                      {definition.kind === 'number' && definition.withSlider ? (
                        <div className="number-control">
                          <input
                            aria-label={`${definition.label} 滑块`}
                            type="range"
                            min={definition.min}
                            max={definition.max}
                            step={definition.step}
                            value={asNumber(value)}
                            onChange={event => updateValue(definition.key, Number(event.target.value))}
                          />
                          <input
                            id={definition.key}
                            type="number"
                            min={definition.min}
                            max={definition.max}
                            step={definition.step}
                            value={asNumber(value)}
                            onChange={event => updateValue(definition.key, Number(event.target.value))}
                          />
                        </div>
                      ) : null}

                      {definition.kind === 'number' && !definition.withSlider ? (
                        <input
                          id={definition.key}
                          type="number"
                          min={definition.min}
                          max={definition.max}
                          step={definition.step}
                          value={asNumber(value)}
                          onChange={event => updateValue(definition.key, Number(event.target.value))}
                        />
                      ) : null}

                      {definition.kind === 'text' ? (
                        <input
                          id={definition.key}
                          type="text"
                          value={String(value)}
                          onChange={event => updateValue(definition.key, event.target.value)}
                        />
                      ) : null}

                      {definition.kind === 'secret' ? (
                        <div className="secret-control">
                          <input
                            id={definition.key}
                            type="password"
                            value={String(value)}
                            autoComplete="off"
                            placeholder="输入新密钥以覆盖当前值"
                            onFocus={() => field && handleSecretFocus(field)}
                            onBlur={() => field && handleSecretBlur(field)}
                            onChange={event => updateValue(definition.key, event.target.value)}
                          />
                          <button
                            type="button"
                            title={revealedSecrets[definition.key] ? '隐藏脱敏预览' : '显示脱敏预览'}
                            onClick={() => setRevealedSecrets(current => ({
                              ...current,
                              [definition.key]: !current[definition.key],
                            }))}
                          >
                            {revealedSecrets[definition.key] ? <EyeOff size={16} /> : <Eye size={16} />}
                          </button>
                          {revealedSecrets[definition.key] ? (
                            <p className="secret-preview">当前预览：{secretPreview}</p>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <footer className="settings-actions">
        <p aria-live="polite">
          {dirtyKeys.length ? `有 ${dirtyKeys.length} 项待保存修改。` : '当前没有未保存的配置变更。'}
        </p>
        <div>
          <button type="button" className="settings-secondary-button" onClick={handleReset} disabled={actionState !== 'idle'}>
            <RotateCcw size={15} />{actionState === 'resetting' ? '重置中' : '重置为默认 / 环境变量'}
          </button>
          <button
            type="button"
            className="settings-primary-button"
            onClick={handleSave}
            disabled={actionState !== 'idle' || !Object.keys(dirtyPayload).length}
          >
            <Save size={15} />{actionState === 'saving' ? '保存中' : '保存更改'}
          </button>
        </div>
      </footer>
    </section>
  );
}
