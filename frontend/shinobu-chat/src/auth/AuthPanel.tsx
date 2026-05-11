import { useState } from 'react';
import type { AuthSession } from '../types';

type AuthPanelProps = {
  onRegister: (payload: { email: string; password: string; display_name?: string }) => Promise<{ id: string; email: string; display_name?: string | null }>;
  onLogin: (payload: { email: string; password: string }) => Promise<AuthSession>;
  onSession: (session: AuthSession) => void;
};

export function AuthPanel({ onRegister, onLogin, onSession }: AuthPanelProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === 'register') {
        await onRegister({ email, password, display_name: displayName || undefined });
      }
      const session = await onLogin({ email, password });
      onSession({ ...session, displayName: displayName || session.displayName });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Authentication failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="auth-panel">
      <div className="auth-copy">
        <span className="brand-mark">忍</span>
        <h1>ShinobuChat</h1>
        <p>登录后进入带 Live2D 桌宠宿主能力的聊天工作台。</p>
      </div>
      <div className="auth-tabs" role="tablist">
        <button className={mode === 'login' ? 'is-active' : ''} type="button" onClick={() => setMode('login')}>登录</button>
        <button className={mode === 'register' ? 'is-active' : ''} type="button" onClick={() => setMode('register')}>注册</button>
      </div>
      <label>
        <span>邮箱</span>
        <input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" />
      </label>
      <label>
        <span>密码</span>
        <input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
      </label>
      {mode === 'register' ? (
        <label>
          <span>显示名</span>
          <input value={displayName} onChange={event => setDisplayName(event.target.value)} />
        </label>
      ) : null}
      {error ? <div className="auth-error">{error}</div> : null}
      <button className="primary-action" type="button" disabled={busy || !email || !password} onClick={submit}>
        {busy ? '处理中...' : mode === 'login' ? '登录' : '注册并登录'}
      </button>
    </section>
  );
}
