import { useEffect, useState } from 'react';
import { getPersonaSettings, updatePersonaSettings } from '../api/persona';
import type {
  PersonaInitiative,
  PersonaSettings,
  PersonaVerbosity,
  PersonaWarmth,
  PersonaWorkStyle,
} from '../types';

type PersonaSettingsPanelProps = {
  accessToken: string;
};

type Option<T extends string> = {
  value: T;
  label: string;
  description: string;
};

type PersonaFieldConfig = {
  key: 'verbosity' | 'warmth' | 'initiative' | 'work_style';
  title: string;
  options: Option<string>[];
};

const verbosityOptions: Option<PersonaVerbosity>[] = [
  { value: 'quiet', label: '安静', description: '少扩展，回复更短' },
  { value: 'balanced', label: '平衡', description: '长度适中，信息完整' },
  { value: 'talkative', label: '话多', description: '可以多解释一点，但不啰嗦' },
];

const warmthOptions: Option<PersonaWarmth>[] = [
  { value: 'calm', label: '平静', description: '语气克制、稳定' },
  { value: 'warm', label: '温柔', description: '更亲近、更有陪伴感' },
  { value: 'playful', label: '俏皮', description: '轻松一点，但不破坏人设' },
];

const initiativeOptions: Option<PersonaInitiative>[] = [
  { value: 'passive', label: '被动', description: '少追问，主要回应你的要求' },
  { value: 'balanced', label: '适度', description: '必要时给出下一步建议' },
  { value: 'proactive', label: '主动', description: '可以主动提醒下一步，但不催促' },
];

const workStyleOptions: Option<PersonaWorkStyle>[] = [
  { value: 'casual', label: '休闲', description: '更像日常聊天' },
  { value: 'focused', label: '专注', description: '更关注效率和任务进展' },
  { value: 'strict', label: '严格', description: '更有执行力，但不能高压训斥' },
];

const personaFieldConfigs: PersonaFieldConfig[] = [
  { key: 'verbosity', title: '话量', options: verbosityOptions },
  { key: 'warmth', title: '温度', options: warmthOptions },
  { key: 'initiative', title: '主动性', options: initiativeOptions },
  { key: 'work_style', title: '工作风格', options: workStyleOptions },
];

export function PersonaSettingsPanel({ accessToken }: PersonaSettingsPanelProps) {
  const [settings, setSettings] = useState<PersonaSettings | null>(null);
  const [draft, setDraft] = useState<Partial<PersonaSettings>>({});
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setState('loading');
    setError(null);
    try {
      const result = await getPersonaSettings(accessToken);
      setSettings(result);
      setDraft(result);
      setState('ready');
    } catch (nextError) {
      setState('error');
      setError(nextError instanceof Error ? nextError.message : '加载角色性格失败');
    }
  };

  useEffect(() => {
    load();
  }, [accessToken]);

  const handleSave = async () => {
    setSaving(true);
    setNotice(null);
    setError(null);
    try {
      const result = await updatePersonaSettings(accessToken, {
        verbosity: draft.verbosity,
        warmth: draft.warmth,
        initiative: draft.initiative,
        work_style: draft.work_style,
      });
      setSettings(result);
      setDraft(result);
      setNotice('角色性格已保存，Shinobu 会记住你的偏好');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  if (state === 'loading') {
    return <div className="settings-skeleton"><span /><span /></div>;
  }

  if (state === 'error' || !settings) {
    return (
      <div className="settings-empty-state">
        <h3>加载失败</h3>
        <p>{error || '请稍后重试'}</p>
        <button type="button" className="settings-secondary-button" onClick={load}>重试</button>
      </div>
    );
  }

  const dirty =
    draft.verbosity !== settings.verbosity ||
    draft.warmth !== settings.warmth ||
    draft.initiative !== settings.initiative ||
    draft.work_style !== settings.work_style;

  return (
    <section className="persona-panel" aria-label="角色性格设置">
      <div className="persona-note">
        <p>调整 Shinobu 的说话风格，保留人设不变，微调表达方式</p>
      </div>
      {error ? <p className="settings-status-error">{error}</p> : null}
      {notice ? <p className="settings-notice">{notice}</p> : null}

      {personaFieldConfigs.map(field => (
        <section className="persona-group" key={field.key}>
          <h3>{field.title}</h3>
          <div className="persona-options">
            {field.options.map(option => (
              <button
                type="button"
                key={option.value}
                className={draft[field.key] === option.value ? 'persona-option is-active' : 'persona-option'}
                onClick={() => setDraft(current => ({ ...current, [field.key]: option.value }))}
              >
                <strong>{option.label}</strong>
                <span>{option.description}</span>
              </button>
            ))}
          </div>
        </section>
      ))}

      <div className="persona-actions">
        <button type="button" className="settings-primary-button" onClick={handleSave} disabled={!dirty || saving}>
          {saving ? '保存中...' : '保存设置'}
        </button>
      </div>
    </section>
  );
}
