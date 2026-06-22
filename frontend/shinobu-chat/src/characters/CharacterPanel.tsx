import { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus, UserPlus, X } from 'lucide-react';
import type { CharacterProfile, ConversationMode } from '../types';
import {
  createCharacterProfile,
  deleteCharacterProfile,
  listCharacterProfiles,
  updateConversationCharacters,
} from '../api/characters';
import { CHARACTER_PRESETS } from './presets';

type CharacterPanelProps = {
  accessToken: string;
  activeCharacters: CharacterProfile[];
  conversationMode?: ConversationMode | null;
  onCharactersChange: (chars: CharacterProfile[]) => void;
};

const MAX_AUXILIARY = 3;

export function CharacterPanel({
  accessToken,
  activeCharacters,
  conversationMode,
  onCharactersChange,
}: CharacterPanelProps) {
  const [profiles, setProfiles] = useState<CharacterProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formPersona, setFormPersona] = useState('');
  const [formColor, setFormColor] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadProfiles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await listCharacterProfiles(accessToken);
      setProfiles(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load character profiles');
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const shinobuProfile = profiles.find((p) => p.name === 'Shinobu');
  const auxiliaryProfiles = profiles.filter((p) => p.name !== 'Shinobu');

  // Work-mode recommended preset names
  const workRecommendedPresets = useMemo(() => new Set(['温柔老师']), []);

  const handleRemove = async (characterId: string) => {
    try {
      setError(null);
      await deleteCharacterProfile(accessToken, characterId);

      const remaining = profiles.filter(
        (p) => p.id !== characterId && p.name !== 'Shinobu',
      );
      const shinobuId = shinobuProfile?.id;
      const allIds = shinobuId
        ? [shinobuId, ...remaining.map((p) => p.id)]
        : remaining.map((p) => p.id);
      await updateConversationCharacters(accessToken, allIds);
      await loadProfiles();

      const updatedAux = profiles.filter(
        (p) => p.id !== characterId && p.name !== 'Shinobu',
      );
      onCharactersChange(updatedAux);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove character');
    }
  };

  const handleAdd = async () => {
    const name = formName.trim();
    const persona = formPersona.trim();
    if (!name || !persona) return;

    if (auxiliaryProfiles.length >= MAX_AUXILIARY) {
      setError(`最多只能添加 ${MAX_AUXILIARY} 个辅助角色`);
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const created = await createCharacterProfile(accessToken, {
        name,
        persona,
        color: formColor.trim() || null,
      });

      const allIds = [...profiles.map((p) => p.id), created.id];
      await updateConversationCharacters(accessToken, allIds);
      await loadProfiles();

      onCharactersChange([...activeCharacters, created]);

      setFormName('');
      setFormPersona('');
      setFormColor('');
      setShowForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create character');
    } finally {
      setSubmitting(false);
    }
  };

  const applyPreset = (preset: (typeof CHARACTER_PRESETS)[number]) => {
    setFormName(preset.name);
    setFormPersona(preset.persona);
    setFormColor(preset.color);
    setShowForm(true);
  };

  if (loading) {
    return (
      <div className="character-panel">
        <div className="settings-skeleton">
          <span />
          <span />
          <span />
        </div>
      </div>
    );
  }

  return (
    <div className="character-panel">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Auxiliary Characters</span>
          <h2>辅助角色</h2>
          <p>为当前会话添加辅助角色，丰富对话体验</p>
        </div>
      </header>

      {error ? <div className="settings-status-error">{error}</div> : null}

      {/* Shinobu card — always present, primary */}
      {shinobuProfile ? (
        <div className="character-card is-primary">
          <div
            className="character-card-avatar"
            style={{ background: '#597fdc' }}
          >
            S
          </div>
          <div className="character-card-body">
            <strong>{shinobuProfile.name}</strong>
            <span>{shinobuProfile.persona}</span>
          </div>
          <span className="character-card-badge">主角色 · 不可移除</span>
        </div>
      ) : (
        <div className="character-card is-primary">
          <div
            className="character-card-avatar"
            style={{ background: '#597fdc' }}
          >
            S
          </div>
          <div className="character-card-body">
            <strong>Shinobu</strong>
            <span>你的主要 AI 陪伴角色</span>
          </div>
          <span className="character-card-badge">主角色 · 不可移除</span>
        </div>
      )}

      {/* Auxiliary character list */}
      {auxiliaryProfiles.length > 0 ? (
        <div className="character-list">
          {auxiliaryProfiles.map((char) => (
            <div key={char.id} className="character-card is-auxiliary">
              <div
                className="character-card-avatar"
                style={{ background: char.color || '#6b7280' }}
              >
                {char.name.slice(0, 1)}
              </div>
              <div className="character-card-body">
                <strong>{char.name}</strong>
                <span>{char.persona}</span>
              </div>
              <button
                type="button"
                className="character-card-remove"
                title={`移除 ${char.name}`}
                onClick={() => handleRemove(char.id)}
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="character-empty">
          还没有辅助角色，添加一个来丰富对话体验。
        </p>
      )}

      {/* Character limit warning */}
      {auxiliaryProfiles.length >= MAX_AUXILIARY ? (
        <div className="character-limit-warning">
          已达到辅助角色上限（{MAX_AUXILIARY}{' '}
          个）。如需添加新角色，请先移除一个现有角色。
        </div>
      ) : null}

      {/* Add character section */}
      <div className="character-add">
        {!showForm ? (
          <div className="character-add-actions">
            <button
              type="button"
              className="settings-primary-button"
              disabled={auxiliaryProfiles.length >= MAX_AUXILIARY}
              onClick={() => setShowForm(true)}
            >
              <UserPlus size={16} />
              添加辅助角色
            </button>

            <div className="character-presets">
              <span>快速模板：</span>
              {CHARACTER_PRESETS.map((preset) => {
                const isWorkRecommended = conversationMode === 'work' && workRecommendedPresets.has(preset.name);
                return (
                  <button
                    key={preset.name}
                    type="button"
                    className={`character-preset-button${isWorkRecommended ? ' is-work-recommended' : ''}`}
                    disabled={auxiliaryProfiles.length >= MAX_AUXILIARY}
                    onClick={() => applyPreset(preset)}
                  >
                    {preset.name}
                    {isWorkRecommended ? <span className="preset-work-badge">推荐</span> : null}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="character-form">
            <h3>创建辅助角色</h3>
            <label>
              角色名称
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="例如：温柔老师"
              />
            </label>
            <label>
              角色设定
              <textarea
                value={formPersona}
                onChange={(e) => setFormPersona(e.target.value)}
                placeholder="描述角色的性格和说话风格..."
                rows={3}
              />
            </label>
            <label>
              代表色（可选）
              <input
                type="text"
                value={formColor}
                onChange={(e) => setFormColor(e.target.value)}
                placeholder="#4f9f6e"
              />
            </label>
            <div className="character-form-actions">
              <button
                type="button"
                className="settings-primary-button"
                disabled={submitting || !formName.trim() || !formPersona.trim()}
                onClick={handleAdd}
              >
                {submitting ? '创建中...' : '确认创建'}
              </button>
              <button
                type="button"
                className="settings-secondary-button"
                onClick={() => {
                  setShowForm(false);
                  setFormName('');
                  setFormPersona('');
                  setFormColor('');
                }}
                disabled={submitting}
              >
                取消
              </button>
            </div>
          </div>
        )}
      </div>

      <p className="character-note">辅助角色仅参与当前会话，不会写入长期记忆</p>
    </div>
  );
}
