import { useEffect, useState } from 'react';
import { fetchCharacterCard, updateCharacterCard } from '../api/client';
import type { CharacterCard, ToneSettings } from '../types';

type CharacterEditorProps = {
  userId: string;
};

const defaultTone: ToneSettings = {
  warmth: 0.8,
  sharpness: 0.3,
  formality: 0.4,
};

const toneLabels: Record<keyof ToneSettings, string> = {
  warmth: 'Warmth',
  sharpness: 'Sharpness',
  formality: 'Formality',
};

export function CharacterEditor({ userId }: CharacterEditorProps) {
  const [card, setCard] = useState<CharacterCard | null>(null);
  const [tone, setTone] = useState<ToneSettings>(defaultTone);
  const [extra, setExtra] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    fetchCharacterCard(userId)
      .then(nextCard => {
        if (cancelled) return;
        setCard(nextCard);
        setTone(nextCard.tone);
        setExtra(nextCard.system_prompt_extra || '');
      })
      .catch(nextError => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : 'Failed to load character');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const updateTone = (key: keyof ToneSettings, value: number) => {
    setTone(current => ({ ...current, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const nextCard = await updateCharacterCard(userId, {
        tone,
        system_prompt_extra: extra,
      });
      setCard(nextCard);
      setTone(nextCard.tone);
      setExtra(nextCard.system_prompt_extra || '');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to save character');
    } finally {
      setSaving(false);
    }
  };

  if (!card && !error) {
    return (
      <section className="character-editor" aria-label="Character settings">
        <h2>Character</h2>
        <p>Loading...</p>
      </section>
    );
  }

  return (
    <section className="character-editor" aria-label="Character settings">
      <header>
        <div>
          <h2>Character</h2>
          <p>{card?.name || 'Shinobu'}</p>
        </div>
      </header>

      {(['warmth', 'sharpness', 'formality'] as const).map(key => (
        <label key={key}>
          <span>{toneLabels[key]} ({tone[key].toFixed(1)})</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={tone[key]}
            onChange={event => updateTone(key, Number(event.target.value))}
          />
        </label>
      ))}

      <label>
        <span>Custom prompt</span>
        <textarea
          value={extra}
          onChange={event => setExtra(event.target.value)}
          placeholder="Extra character instructions..."
          rows={5}
        />
      </label>

      {error ? <p className="character-editor-error">{error}</p> : null}

      <button className="primary-action" type="button" onClick={handleSave} disabled={saving}>
        {saving ? 'Saving...' : 'Save character'}
      </button>
    </section>
  );
}
