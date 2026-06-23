import { useState, useEffect, useCallback } from 'react';
import { Save, Shield, MonitorPlay, Globe, Bot, Wrench } from 'lucide-react';
import {
  getLocalAgentSettings,
  patchLocalAgentSettings,
  type LocalAgentSettings,
} from '../../api/localAgentSettings';

interface Props {
  accessToken: string;
}

const DEFAULTS: LocalAgentSettings = {
  local_launcher_enabled: true,
  browser_reader_enabled: true,
  browser_automation_enabled: false,
  mcp_enabled: false,
  allow_direct_open_music: true,
  allow_direct_open_browser: true,
  require_confirm_for_executable: true,
  require_confirm_for_unknown_url: true,
};

export default function LocalAgentPermissionPanel({ accessToken }: Props) {
  const [settings, setSettings] = useState<LocalAgentSettings>(DEFAULTS);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadState('loading');
    try {
      const s = await getLocalAgentSettings(accessToken);
      setSettings(s);
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const toggle = (key: keyof LocalAgentSettings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      const updated = await patchLocalAgentSettings(accessToken, settings);
      setSettings(updated);
      setNotice('设置已保存');
    } catch {
      setNotice('保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  if (loadState === 'loading') {
    return (
      <section className="local-agent-permission-panel">
        <div className="settings-skeleton"><span /><span /><span /></div>
      </section>
    );
  }

  if (loadState === 'error') {
    return (
      <section className="local-agent-permission-panel">
        <p className="settings-status-error">无法加载权限设置。</p>
      </section>
    );
  }

  const ToggleRow = ({
    icon: Icon,
    label,
    desc,
    keyName,
    disabled = false,
  }: {
    icon: typeof Shield;
    label: string;
    desc: string;
    keyName: keyof LocalAgentSettings;
    disabled?: boolean;
  }) => (
    <div className="config-field">
      <div className="config-field-copy">
        <label><Icon size={16} /> {label}</label>
        <p>{desc}</p>
      </div>
      <div className="config-control">
        <button
          type="button"
          className={`settings-toggle ${settings[keyName] ? 'is-on' : ''}`}
          onClick={() => toggle(keyName)}
          disabled={disabled}
          aria-label={`${label}：${settings[keyName] ? '已开启' : '已关闭'}`}
          role="switch"
          aria-checked={settings[keyName]}
        >
          <span aria-hidden="true" />
        </button>
      </div>
    </div>
  );

  return (
    <section className="local-agent-permission-panel" aria-label="权限中心">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">Permissions</span>
          <h2>权限中心</h2>
          <p>控制本地应用、浏览器和自动化能力</p>
        </div>
        <button
          className="settings-primary-button"
          onClick={save}
          disabled={saving}
          aria-label="保存权限设置"
        >
          <Save size={15} /> {saving ? '保存中...' : '保存权限设置'}
        </button>
      </header>

      {notice && (
        <p className={notice.includes('失败') ? 'settings-status-error' : 'settings-notice'}>
          {notice}
        </p>
      )}

      <div className="permission-section">
        <h3><MonitorPlay size={16} /> 本地应用</h3>
        <ToggleRow
          icon={MonitorPlay}
          label="Local Launcher"
          desc={'允许 Shinobu 通过聊天启动本地应用。关闭后“我想听歌”等快捷指令将不执行。'}
          keyName="local_launcher_enabled"
        />
        {settings.local_launcher_enabled && (
          <>
            <ToggleRow
              icon={MonitorPlay}
              label="允许直接打开音乐"
              desc="允许在未确认时直接打开音乐应用"
              keyName="allow_direct_open_music"
            />
            <ToggleRow
              icon={MonitorPlay}
              label="允许直接打开浏览器"
              desc="允许在未确认时直接打开浏览器"
              keyName="allow_direct_open_browser"
            />
            <ToggleRow
              icon={MonitorPlay}
              label="可执行文件需确认"
              desc="打开 .exe/.bat/.ps1 等可执行文件前需二次确认"
              keyName="require_confirm_for_executable"
            />
            <ToggleRow
              icon={MonitorPlay}
              label="未知 URL 需确认"
              desc="打开不在可信列表中的 URL 前需二次确认"
              keyName="require_confirm_for_unknown_url"
            />
          </>
        )}
        {!settings.local_launcher_enabled && (
          <p className="permission-disabled-hint">
            Local Launcher 已关闭。所有本地应用启动和快捷指令将不可用。
          </p>
        )}
      </div>

      <div className="permission-section">
        <h3><Globe size={16} /> 浏览器能力</h3>
        <ToggleRow
          icon={Globe}
          label="Browser Reader"
          desc="允许网页搜索、读取和总结。关闭后浏览器阅读功能将不可用。"
          keyName="browser_reader_enabled"
        />
        <ToggleRow
          icon={Bot}
          label="Browser Automation"
          desc="允许浏览器自动操作（打开页面、截图等）。默认关闭。开启后仍需要逐次确认。"
          keyName="browser_automation_enabled"
        />
        {!settings.browser_automation_enabled && (
          <p className="permission-disabled-hint">
            Browser Automation 默认关闭。自动点击、下载等操作需要先启用此开关。
          </p>
        )}
      </div>

      <div className="permission-section">
        <h3><Wrench size={16} /> MCP 集成</h3>
        <ToggleRow
          icon={Wrench}
          label="MCP Adapter"
          desc="允许外部 AI Agent（如 Claude Code）通过 MCP 协议调用本系统工具。默认关闭。"
          keyName="mcp_enabled"
        />
        {!settings.mcp_enabled && (
          <p className="permission-disabled-hint">
            MCP 默认关闭。MCP 是给外部 Agent 使用的适配层，只暴露低风险工具。
          </p>
        )}
      </div>
    </section>
  );
}
