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
  { value: 'quiet', label: '??', description: '?????????' },
  { value: 'balanced', label: '??', description: '?????????' },
  { value: 'talkative', label: '??', description: '???????????' },
];

const warmthOptions: Option<PersonaWarmth>[] = [
  { value: 'calm', label: '??', description: '????????????' },
  { value: 'warm', label: '??', description: '???????????' },
  { value: 'playful', label: '??', description: '????????????' },
];

const initiativeOptions: Option<PersonaInitiative>[] = [
  { value: 'passive', label: '??', description: '????????' },
  { value: 'balanced', label: '??', description: '???????????' },
  { value: 'proactive', label: '??', description: '???????????' },
];

const workStyleOptions: Option<PersonaWorkStyle>[] = [
  { value: 'casual', label: '??', description: '??????????' },
  { value: 'focused', label: '??', description: '????????' },
  { value: 'strict', label: '??', description: '?????????' },
];

const personaFieldConfigs: PersonaFieldConfig[] = [
  { key: 'verbosity', title: '????', options: verbosityOptions },
  { key: 'warmth', title: '??', options: warmthOptions },
  { key: 'initiative', title: '????', options: initiativeOptions },
  { key: 'work_style', title: '????', options: workStyleOptions },
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
      setError(nextError instanceof Error ? nextError.message : '??????????');
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
      setNotice('???????????? Shinobu ??????');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : '??????????');
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
        <h3>????????????</h3>
        <p>{error || '??????'}</p>
        <button type="button" className="settings-secondary-button" onClick={load}>????</button>
      </div>
    );
  }

  const dirty =
    draft.verbosity !== settings.verbosity ||
    draft.warmth !== settings.warmth ||
    draft.initiative !== settings.initiative ||
    draft.work_style !== settings.work_style;

  return (
    <section className="persona-panel" aria-label="??????">
      <div className="persona-note">
        <p>??????????????????????? Shinobu ??????</p>
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
          {saving ? '???' : '??????'}
        </button>
      </div>
    </section>
  );
}
