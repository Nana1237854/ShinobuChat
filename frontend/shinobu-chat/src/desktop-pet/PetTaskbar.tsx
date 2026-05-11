import clsx from 'clsx';
import type { ReactNode } from 'react';
import { Camera, Candy, Hand, Hammer, Settings } from 'lucide-react';
import type { AvatarTool } from '../types';

type PetTaskbarProps = {
  activeTool: AvatarTool | null;
  onToolSelect: (tool: AvatarTool) => void;
  onOpenSettings: () => void;
  onScreenshot: () => void;
};

const tools: Array<{ id: AvatarTool; label: string; icon: ReactNode }> = [
  { id: 'lollipop', label: 'Lollipop', icon: <Candy size={18} /> },
  { id: 'fist', label: 'Poke', icon: <Hand size={18} /> },
  { id: 'hammer', label: 'Hammer', icon: <Hammer size={18} /> },
];

export function PetTaskbar({ activeTool, onToolSelect, onOpenSettings, onScreenshot }: PetTaskbarProps) {
  return (
    <div className="pet-taskbar" aria-label="Pet taskbar">
      {tools.map(tool => (
        <button
          key={tool.id}
          type="button"
          className={clsx(activeTool === tool.id && 'is-active')}
          title={tool.label}
          aria-pressed={activeTool === tool.id}
          onClick={() => onToolSelect(tool.id)}
        >
          {tool.icon}
        </button>
      ))}
      <span className="taskbar-divider" />
      <button type="button" title="Screenshot" onClick={onScreenshot}><Camera size={18} /></button>
      <button type="button" title="Pet settings" onClick={onOpenSettings}><Settings size={18} /></button>
    </div>
  );
}
