import { useEffect, useState, type MouseEvent } from 'react';
import { BookOpen, Bot, Clock3, Cpu, Globe, MonitorPlay, Palette, Puzzle, ScrollText, Settings2, Shield, SunMoon, Users, Wrench, X } from 'lucide-react';
import { CharacterEditor } from '../chat/CharacterEditor';
import { PetSettingsPanel } from '../desktop-pet/PetSettingsPanel';
import { GoalTrackerPanel } from '../goals/GoalTrackerPanel';
import { MemoryTimelinePanel } from '../memories/MemoryTimelinePanel';
import { DiaryPanel } from '../diaries/DiaryPanel';
import { CharacterPanel } from '../characters/CharacterPanel';
import type { BackgroundItem, CharacterProfile, Live2DModelItem, PetSettings } from '../types';
import { ConfigPanel } from './ConfigPanel';
import { PersonaSettingsPanel } from './PersonaSettingsPanel';
import { SkillPanel } from './SkillPanel';
import { LocalAppsPanel } from '../components/settings/LocalAppsPanel';
import BrowserReaderPanel from '../components/settings/BrowserReaderPanel';
import LocalAgentPermissionPanel from '../components/settings/LocalAgentPermissionPanel';
import ActionLogsPanel from '../components/settings/ActionLogsPanel';
import McpSettingsPanel from '../components/settings/McpSettingsPanel';
import { ModeSwitch } from '../modes/ModeSwitch';
import type { ConversationMode } from '../types';

export type SettingsTab = 'appearance' | 'persona' | 'models' | 'skills' | 'localApps' | 'memories' | 'goals' | 'mode' | 'diaries' | 'characters' | 'browser' | 'permissions' | 'actionLogs' | 'mcp';

type SettingsPageProps = {
  accessToken: string;
  userId: string;
  petSettings: PetSettings;
  models: Live2DModelItem[];
  backgrounds: BackgroundItem[];
  initialTab?: SettingsTab;
  conversationMode: ConversationMode | null;
  activeCharacters?: CharacterProfile[];
  onPetSettingsChange: (settings: PetSettings) => void;
  onRefreshModels: () => void;
  onGoalsChanged?: () => void;
  onModeChange: (mode: ConversationMode) => void;
  onCharactersChange?: (chars: CharacterProfile[]) => void;
  onClose: () => void;
};

type TabDefinition = {
  id: SettingsTab;
  label: string;
  note: string;
  icon: typeof Palette;
};

const tabs: TabDefinition[] = [
  { id: 'appearance', label: 'Live2D 外观', note: '模型、舞台与位置', icon: Palette },
  { id: 'persona', label: '角色性格', note: '保留人设，微调表达', icon: Bot },
  { id: 'models', label: 'AI 模型', note: '模型、密钥与语音服务', icon: Cpu },
  { id: 'skills', label: '技能管理', note: '安装、编辑与启停 Skill', icon: Puzzle },
  { id: 'localApps', label: '本地应用', note: '配置可调用的本地程序', icon: MonitorPlay },
  { id: 'memories', label: '记忆时间线', note: '搜索与回放长期记忆', icon: Settings2 },
  { id: 'goals', label: '长期目标', note: '陪伴式追踪与 check-in', icon: Clock3 },
  { id: 'mode', label: '情景模式', note: '切换陪伴 / 工作 / 专注 / 夜间', icon: SunMoon },
  { id: 'diaries', label: 'Shinobu 日记', note: '每日回顾与心情记录', icon: BookOpen },
  { id: 'characters', label: '辅助角色', note: '管理会话角色', icon: Users },
  { id: 'browser', label: '浏览器能力', note: '搜索、读取与网页总结', icon: Globe },
  { id: 'permissions', label: '权限中心', note: 'Agent 能力开关与安全', icon: Shield },
  { id: 'actionLogs', label: '执行日志', note: '本地与浏览器动作记录', icon: ScrollText },
  { id: 'mcp', label: 'MCP 集成', note: '外部 Agent 适配层', icon: Wrench },
];

export function SettingsPage({
  accessToken,
  userId,
  petSettings,
  models,
  backgrounds,
  initialTab = 'appearance',
  conversationMode,
  activeCharacters = [],
  onPetSettingsChange,
  onRefreshModels,
  onGoalsChanged,
  onModeChange,
  onCharactersChange,
  onClose,
}: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<SettingsTab>(initialTab);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleOverlayClick = () => {
    onClose();
  };

  const stopOverlayClose = (event: MouseEvent<HTMLElement>) => {
    event.stopPropagation();
  };

  return (
    <div className="settings-overlay" role="presentation" onClick={handleOverlayClick}>
      <section
        className="settings-page"
        role="dialog"
        aria-modal="true"
        aria-label="ShinobuChat 设置"
        onClick={stopOverlayClose}
      >
        <aside className="settings-nav">
          <header>
            <span className="settings-nav-mark"><Settings2 size={18} /></span>
            <div>
              <strong>设置</strong>
              <small>ShinobuChat control room</small>
            </div>
          </header>
          <nav aria-label="设置分类">
            {tabs.map(tab => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  type="button"
                  className={activeTab === tab.id ? 'is-active' : ''}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <Icon size={18} />
                  <span>
                    <strong>{tab.label}</strong>
                    <small>{tab.note}</small>
                  </span>
                </button>
              );
            })}
          </nav>
          <footer>
            <span>USER SCOPE</span>
            <strong>{userId.slice(0, 8)}</strong>
            <p>配置、记忆、目标与用户自定义 Skill 都只作用于当前账户。</p>
          </footer>
        </aside>

        <main className="settings-main">
          <button type="button" className="settings-close" title="关闭设置" onClick={onClose}>
            <X size={18} />
          </button>

          {activeTab === 'appearance' ? (
            <div className="settings-legacy-panel">
              <header className="settings-content-header">
                <div>
                  <span className="settings-eyebrow">Stage appearance</span>
                  <h2>Live2D 外观</h2>
                  <p>统一调整模型、背景、透明度和舞台位置，不影响现有聊天与角色编辑流程。</p>
                </div>
              </header>
              <PetSettingsPanel
                settings={petSettings}
                models={models}
                backgrounds={backgrounds}
                onChange={onPetSettingsChange}
                onRefreshModels={onRefreshModels}
                onClose={onClose}
              />
            </div>
          ) : null}

          {activeTab === 'persona' ? (
            <div className="settings-legacy-panel persona-tab-stack">
              <header className="settings-content-header">
                <div>
                  <span className="settings-eyebrow">Character expression</span>
                  <h2>角色性格</h2>
                  <p>先用轻量 Persona 设置调整说话风格，再保留原有角色编辑能力，避免破坏已经能用的设定流。</p>
                </div>
              </header>
              <PersonaSettingsPanel accessToken={accessToken} />
              <div className="persona-legacy-card">
                <div className="persona-note">
                  <p>下面仍然保留旧版角色编辑器，方便继续调整 tone 与补充 prompt。</p>
                </div>
                <CharacterEditor userId={userId} />
              </div>
            </div>
          ) : null}

          {activeTab === 'models' ? <ConfigPanel accessToken={accessToken} /> : null}
          {activeTab === 'skills' ? <SkillPanel accessToken={accessToken} /> : null}
          {activeTab === 'localApps' ? <LocalAppsPanel accessToken={accessToken} /> : null}
          {activeTab === 'memories' ? <MemoryTimelinePanel accessToken={accessToken} /> : null}
          {activeTab === 'goals' ? <GoalTrackerPanel accessToken={accessToken} onGoalsChanged={onGoalsChanged} /> : null}
          {activeTab === 'mode' ? (
            <div className="settings-legacy-panel">
              <header className="settings-content-header">
                <div>
                  <span className="settings-eyebrow">Conversation mode</span>
                  <h2>情景模式</h2>
                  <p>切换即时生效，当前模式会影响 Shinobu 的回复风格和通知频率。</p>
                </div>
              </header>
              <ModeSwitch
                accessToken={accessToken}
                mode={conversationMode}
                onModeChange={onModeChange}
              />
            </div>
          ) : null}

          {activeTab === 'diaries' ? (
            <div className="settings-legacy-panel">
              <DiaryPanel accessToken={accessToken} />
            </div>
          ) : null}

          {activeTab === 'characters' ? (
            <div className="settings-legacy-panel">
              <CharacterPanel
                accessToken={accessToken}
                activeCharacters={activeCharacters}
                conversationMode={conversationMode}
                onCharactersChange={onCharactersChange || (() => {})}
              />
            </div>
          ) : null}

          {activeTab === 'browser' ? (
            <div className="settings-legacy-panel">
              <BrowserReaderPanel accessToken={accessToken} />
            </div>
          ) : null}

          {activeTab === 'permissions' ? (
            <div className="settings-legacy-panel">
              <LocalAgentPermissionPanel accessToken={accessToken} />
            </div>
          ) : null}

          {activeTab === 'actionLogs' ? (
            <div className="settings-legacy-panel">
              <ActionLogsPanel accessToken={accessToken} />
            </div>
          ) : null}

          {activeTab === 'mcp' ? (
            <div className="settings-legacy-panel">
              <McpSettingsPanel accessToken={accessToken} />
            </div>
          ) : null}
        </main>
      </section>
    </div>
  );
}
