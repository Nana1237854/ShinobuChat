import { useState, useEffect, useCallback } from 'react';
import { Wrench, ShieldCheck, ShieldOff, Terminal, ExternalLink } from 'lucide-react';
import { getMcpStatus, patchMcpSettings, type McpStatus } from '../../api/mcp';

interface Props {
  accessToken: string;
}

export default function McpSettingsPanel({ accessToken }: Props) {
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [toggling, setToggling] = useState(false);

  const load = useCallback(async () => {
    setLoadState('loading');
    try {
      const s = await getMcpStatus(accessToken);
      setStatus(s);
      setLoadState('ready');
    } catch {
      setLoadState('error');
    }
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const toggleEnabled = async () => {
    if (!status) return;
    setToggling(true);
    try {
      const updated = await patchMcpSettings(accessToken, { enabled: !status.enabled });
      setStatus(updated);
    } catch {
      // ignore
    } finally {
      setToggling(false);
    }
  };

  if (loadState === 'loading') {
    return (
      <section className="mcp-settings-panel">
        <div className="settings-skeleton"><span /><span /><span /></div>
      </section>
    );
  }

  if (loadState === 'error' || !status) {
    return (
      <section className="mcp-settings-panel" aria-label="MCP 集成">
        <header className="settings-content-header">
          <div>
            <span className="settings-eyebrow">MCP Integration</span>
            <h2>MCP 集成</h2>
            <p>MCP Adapter 尚未启用，预计在 F14.5 阶段开放。</p>
          </div>
        </header>
      </section>
    );
  }

  return (
    <section className="mcp-settings-panel" aria-label="MCP 集成">
      <header className="settings-content-header">
        <div>
          <span className="settings-eyebrow">MCP Integration</span>
          <h2>MCP 集成</h2>
          <p>
            MCP 是给 Claude Code / Claude Desktop 等外部 Agent 使用的适配层。
            默认关闭，只暴露低风险工具，不暴露 shell、安装包运行、文件写入等高风险能力。
          </p>
        </div>
      </header>

      {/* Status card */}
      <div className={`mcp-status-card ${status.enabled ? 'mcp-status-card--on' : 'mcp-status-card--off'}`}>
        <div className="mcp-status-header">
          {status.enabled ? (
            <ShieldCheck size={20} color="var(--accent-green)" />
          ) : (
            <ShieldOff size={20} color="var(--text-muted)" />
          )}
          <span>MCP {status.enabled ? '已启用' : '已关闭'}</span>
        </div>
        <p className="mcp-status-message">{status.message}</p>
        <button
          className={status.enabled ? 'settings-secondary-button' : 'settings-primary-button'}
          onClick={toggleEnabled}
          disabled={toggling}
          aria-label={status.enabled ? '禁用 MCP' : '启用 MCP'}
        >
          <Wrench size={14} /> {status.enabled ? '禁用 MCP' : '启用 MCP'}
        </button>
      </div>

      {/* Safe tools */}
      <div className="mcp-tool-list">
        <h3>
          <ShieldCheck size={16} /> 允许暴露的工具 ({status.safe_tools.length})
        </h3>
        <ul>
          {status.safe_tools.map((t) => (
            <li key={t} className="mcp-tool-item mcp-tool-item--safe">
              <code>{t}</code>
            </li>
          ))}
        </ul>
      </div>

      {/* Blocked tools */}
      <div className="mcp-tool-list">
        <h3>
          <ShieldOff size={16} /> 不暴露的工具 ({status.blocked_tools.length})
        </h3>
        <ul>
          {status.blocked_tools.map((t) => (
            <li key={t} className="mcp-tool-item mcp-tool-item--blocked">
              <code>{t}</code>
            </li>
          ))}
        </ul>
      </div>

      {/* Startup command */}
      <div className="mcp-startup">
        <h3>启动命令</h3>
        <p>如果后端已配置 MCP，可以使用以下命令启动：</p>
        <pre className="mcp-startup-cmd">
          <Terminal size={14} /> python -m app.mcp.server
        </pre>
        <p className="mcp-startup-note">
          需要先设置环境变量 <code>SC_MCP_ENABLED=true</code>
        </p>
      </div>
    </section>
  );
}
