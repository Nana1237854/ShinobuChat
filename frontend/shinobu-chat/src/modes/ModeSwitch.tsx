import { useCallback, useEffect, useState } from 'react';
import type { ConversationMode } from '../types';
import { getConversationMode, updateConversationMode } from '../api/modes';

type ModeSwitchProps = {
  accessToken: string;
  mode: ConversationMode | null;
  onModeChange: (mode: ConversationMode) => void;
};

type ModeDef = {
  value: ConversationMode;
  label: string;
  description: string;
};

const modes: ModeDef[] = [
  { value: 'companion', label: '陪伴', description: '保持 Shinobu 的日常陪伴感' },
  { value: 'work', label: '工作', description: '优先整理任务、步骤和结论' },
  { value: 'focus', label: '专注', description: '减少闲聊，只保留必要提醒' },
  { value: 'night', label: '夜间', description: '降低打扰，回复更轻柔' },
];

export function ModeSwitch({ accessToken, mode, onModeChange }: ModeSwitchProps) {
  const [switching, setSwitching] = useState<ConversationMode | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSwitch = useCallback(
    async (next: ConversationMode) => {
      if (!mode || switching || next === mode) return;
      const previous = mode;
      setSwitching(next);
      setError(null);
      try {
        await updateConversationMode(accessToken, next);
        onModeChange(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : '切换模式失败');
      } finally {
        setSwitching(null);
      }
    },
    [accessToken, mode, switching, onModeChange],
  );

  return (
    <div className="mode-switch">
      <h3 className="mode-switch-title">情景模式</h3>
      <p className="mode-switch-subtitle">
        切换即时生效，当前模式会影响 Shinobu 的回复风格和通知频率。
      </p>
      {error ? (
        <div className="mode-switch-error">{error}</div>
      ) : null}
      <div className="mode-options" role="radiogroup" aria-label="情景模式">
        {modes.map(def => {
          const active = mode === def.value;
          const busy = switching === def.value;
          return (
            <button
              key={def.value}
              type="button"
              role="radio"
              aria-checked={active}
              className={['mode-option', active ? 'is-active' : '', busy ? 'is-switching' : '']
                .filter(Boolean)
                .join(' ')}
              disabled={switching !== null}
              onClick={() => handleSwitch(def.value)}
            >
              <strong>{def.label}</strong>
              <span>{def.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function useConversationMode(accessToken: string | null) {
  const [mode, setMode] = useState<ConversationMode | null>(null);
  const [modeLoading, setModeLoading] = useState(false);
  const [modeError, setModeError] = useState<string | null>(null);

  const loadMode = useCallback(async () => {
    if (!accessToken) {
      setMode(null);
      return;
    }
    setModeLoading(true);
    setModeError(null);
    try {
      const settings = await getConversationMode(accessToken);
      setMode(settings.mode);
    } catch (err) {
      setModeError(err instanceof Error ? err.message : '无法获取情景模式');
    } finally {
      setModeLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    loadMode();
  }, [loadMode]);

  const changeMode = useCallback(
    async (next: ConversationMode) => {
      if (!accessToken || next === mode) return;
      const previous = mode;
      setMode(next);
      try {
        await updateConversationMode(accessToken, next);
      } catch {
        setMode(previous);
        throw new Error('切换模式失败，已恢复');
      }
    },
    [accessToken, mode],
  );

  return { mode, modeLoading, modeError, changeMode, reload: loadMode };
}

export function getModePlaceholder(mode: ConversationMode | null): string {
  switch (mode) {
    case 'work':
      return '输入任务或问题，我会优先整理步骤...';
    case 'focus':
      return '输入消息（专注模式中）...';
    case 'night':
      return '轻声输入消息...';
    default:
      return '输入消息...';
  }
}

export function getModeStatusLabel(mode: ConversationMode | null): string {
  switch (mode) {
    case 'work':
      return '工作模式';
    case 'focus':
      return '专注模式';
    case 'night':
      return '夜间模式';
    default:
      return '陪伴模式';
  }
}
