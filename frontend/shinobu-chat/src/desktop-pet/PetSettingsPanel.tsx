import { X } from 'lucide-react';
import type { BackgroundItem, Live2DModelItem, PetSettings, ReminderMode } from '../types';

type PetSettingsPanelProps = {
  settings: PetSettings;
  models: Live2DModelItem[];
  backgrounds: BackgroundItem[];
  onChange: (settings: PetSettings) => void;
  onRefreshModels: () => void;
  onClose: () => void;
};

const reminderModes: Array<{ value: ReminderMode; label: string }> = [
  { value: 'none', label: 'None' },
  { value: 'toast', label: 'Toast' },
  { value: 'sound', label: 'Sound' },
];

export function PetSettingsPanel({
  settings,
  models,
  backgrounds,
  onChange,
  onRefreshModels,
  onClose,
}: PetSettingsPanelProps) {
  return (
    <section className="pet-settings-panel" aria-label="Pet settings">
      <header>
        <h2>桌宠设置</h2>
        <button type="button" title="Close" onClick={onClose}><X size={16} /></button>
      </header>
      <label>
        <span>Live2D 模型</span>
        <select
          value={settings.modelId || ''}
          onChange={event => onChange({ ...settings, modelId: event.target.value || undefined })}
        >
          <option value="">无模型占位</option>
          {models.map(model => <option key={model.id} value={model.id}>{model.name}</option>)}
        </select>
      </label>
      <label>
        <span>背景</span>
        <select
          value={settings.backgroundId}
          onChange={event => onChange({ ...settings, backgroundId: event.target.value })}
        >
          {backgrounds.map(background => <option key={background.id} value={background.id}>{background.name}</option>)}
        </select>
      </label>
      <label>
        <span>透明度 {Math.round(settings.opacity * 100)}%</span>
        <input
          type="range"
          min="0.25"
          max="1"
          step="0.01"
          value={settings.opacity}
          onChange={event => onChange({ ...settings, opacity: Number(event.target.value) })}
        />
      </label>
      <label>
        <span>提醒方式</span>
        <select
          value={settings.reminderMode}
          onChange={event => onChange({ ...settings, reminderMode: event.target.value as ReminderMode })}
        >
          {reminderModes.map(mode => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
        </select>
      </label>
      <button
        className="secondary-action"
        type="button"
        onClick={onRefreshModels}
      >
        刷新模型列表
      </button>
      <button
        className="secondary-action"
        type="button"
        onClick={() => onChange({ ...settings, scale: 0.32, x: 52, y: 72 })}
      >
        重置位置
      </button>
    </section>
  );
}
