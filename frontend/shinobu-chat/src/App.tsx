import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  History,
  LogOut,
  MessageSquarePlus,
  MoreHorizontal,
  Music2,
  PanelLeft,
  RefreshCw,
  Search,
  Settings,
  Sparkles,
  UserRoundCog,
} from 'lucide-react';
import { AuthPanel } from './auth/AuthPanel';
import { ConversationList } from './chat/ConversationList';
import { MessageList } from './chat/MessageList';
import { Composer } from './chat/Composer';
import { CharacterEditor } from './chat/CharacterEditor';
import { mergeServerMessages } from './chat/messageState';
import { Live2DStage } from './live2d/Live2DStage';
import { LIP_SYNC_FFT_SIZE, LIP_SYNC_NOISE_FLOOR, LIP_SYNC_SCALE, LIP_SYNC_SMOOTHING, ANALYSER_SMOOTHING } from './live2d/lipSync';
import { PetTaskbar } from './desktop-pet/PetTaskbar';
import { PetSettingsPanel } from './desktop-pet/PetSettingsPanel';
import { MusicPlayer } from './media/MusicPlayer';
import { captureScreen } from './media/screenshot';
import {
  listConversations,
  listMessages,
  loginWithDeviceFlow,
  registerUser,
  sendMessageStream,
  synthesizeSpeech,
  transcribeSpeech,
} from './api/client';
import {
  loadBackgrounds,
  loadLive2DModels,
  loadMusicTracks,
} from './live2d/assetManifest';
import {
  defaultPetSettings,
  loadPetSettings,
  savePetSettings,
} from './live2d/settings';
import type {
  ApiMessage,
  AuthSession,
  AvatarTool,
  BackgroundItem,
  ChatMessage,
  Conversation,
  Live2DModelItem,
  MusicTrack,
  PetSettings,
  RouteMode,
} from './types';

const SESSION_KEY = 'shinobu-auth-session';

function loadSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) as AuthSession : null;
  } catch {
    return null;
  }
}

function saveSession(session: AuthSession | null) {
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

function toChatMessage(message: ApiMessage): ChatMessage {
  return { ...message, status: 'sent' };
}

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(() => loadSession());
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem('shinobu-conversation-id'));
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [routeMode, setRouteMode] = useState<RouteMode>(() => (localStorage.getItem('shinobu-route-mode') as RouteMode) || 'auto');
  const [streaming, setStreaming] = useState(false);
  const streamingRef = useRef(streaming);
  const [status, setStatus] = useState('Ready');
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<Live2DModelItem[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [petSettings, setPetSettings] = useState<PetSettings>(() => loadPetSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarPanel, setSidebarPanel] = useState<'history' | 'models' | 'scenes' | null>('history');
  const [activeTool, setActiveTool] = useState<AvatarTool | null>(null);
  const [activeEmotion, setActiveEmotion] = useState<string | null>(null);
  const [petFeedback, setPetFeedback] = useState<string | null>(null);
  const [galgameMode, setGalgameMode] = useState(false);
  const [spokenLines, setSpokenLines] = useState<string[]>([]);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const audioNextRef = useRef(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const lipSyncRef = useRef<((v: number) => void) | null>(null);
  const setLipSyncRef = (fn: (v: number) => void) => { lipSyncRef.current = fn; };
  const mouthRef = useRef(0);
  const lipRafRef = useRef(0);
  const audioEndTimeRef = useRef(0);


  const ensureLipSyncRunning = () => {
    if (lipRafRef.current) return;
    const tick = () => {
      const a = analyserRef.current;
      const fn = lipSyncRef.current;
      const hasAudio = audioEndTimeRef.current > (audioCtxRef.current?.currentTime || 0);
      if (a && fn && hasAudio) {
        const buf = new Uint8Array(a.fftSize);
        a.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const scaled = Math.max(0, Math.min((rms - LIP_SYNC_NOISE_FLOOR) * LIP_SYNC_SCALE, 1));
        mouthRef.current += LIP_SYNC_SMOOTHING * (scaled - mouthRef.current);
        fn(mouthRef.current);
      } else {
        mouthRef.current *= 0.6;
        if (fn) fn(mouthRef.current);
        if (mouthRef.current < 0.01 && !hasAudio) {
          mouthRef.current = 0;
          if (fn) fn(0);
          lipRafRef.current = 0;
          return;
        }
      }
      lipRafRef.current = requestAnimationFrame(tick);
    };
    lipRafRef.current = requestAnimationFrame(tick);
  };

  function playBase64Audio(b64: string) {
    const ac = audioCtxRef.current || (audioCtxRef.current = new AudioContext());
    if (!analyserRef.current) {
      analyserRef.current = ac.createAnalyser();
      analyserRef.current.fftSize = LIP_SYNC_FFT_SIZE;
      analyserRef.current.smoothingTimeConstant = ANALYSER_SMOOTHING;
      analyserRef.current.connect(ac.destination);
    }
    try {
      const binary = atob(b64);
      const buf = new ArrayBuffer(binary.length);
      const view = new Uint8Array(buf);
      for (let i = 0; i < binary.length; i++) view[i] = binary.charCodeAt(i);
      ac.decodeAudioData(buf, (decoded) => {
        const now = ac.currentTime;
        const start = Math.max(now, audioNextRef.current);
        audioNextRef.current = start + decoded.duration;
        audioEndTimeRef.current = Math.max(audioEndTimeRef.current, audioNextRef.current);
        const source = ac.createBufferSource();
        source.buffer = decoded;
        source.connect(analyserRef.current!);
        source.start(start);
        ensureLipSyncRunning();
      }, () => {});
    } catch (_) {}
  }

  const reloadAssets = useCallback(async () => {
    const [nextModels, nextBackgrounds, nextTracks] = await Promise.all([
      loadLive2DModels(),
      loadBackgrounds(),
      loadMusicTracks(),
    ]);
    setModels(nextModels);
    setBackgrounds(nextBackgrounds);
    setTracks(nextTracks);
    setPetSettings(current => {
      const modelId = nextModels.some(item => item.id === current.modelId)
        ? current.modelId
        : nextModels[0]?.id || defaultPetSettings.modelId;
      const backgroundId = nextBackgrounds.some(item => item.id === current.backgroundId)
        ? current.backgroundId
        : nextBackgrounds[0]?.id || defaultPetSettings.backgroundId;
      return { ...current, modelId, backgroundId };
    });
  }, []);

  useEffect(() => {
    reloadAssets().catch(nextError => {
      setError(nextError instanceof Error ? nextError.message : 'Failed to load assets');
    });
  }, [reloadAssets]);

  useEffect(() => {
    if (!import.meta.hot) return undefined;

    const handleLive2DAssetsRefresh = () => {
      reloadAssets().catch(nextError => {
        setError(nextError instanceof Error ? nextError.message : 'Failed to refresh assets');
      });
    };

    import.meta.hot.on('live2d-assets:refresh', handleLive2DAssetsRefresh);
    return () => {
      import.meta.hot?.off('live2d-assets:refresh', handleLive2DAssetsRefresh);
    };
  }, [reloadAssets]);

  useEffect(() => {
    if (!settingsOpen) return;

    reloadAssets().catch(nextError => {
      setError(nextError instanceof Error ? nextError.message : 'Failed to refresh assets');
    });
  }, [reloadAssets, settingsOpen]);

  useEffect(() => {
    savePetSettings(petSettings);
  }, [petSettings]);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  useEffect(() => {
    localStorage.setItem('shinobu-route-mode', routeMode);
  }, [routeMode]);

  useEffect(() => () => {
    if (lipRafRef.current) cancelAnimationFrame(lipRafRef.current);
    if (audioCtxRef.current) audioCtxRef.current.close().catch(() => {});
  }, []);

  const refreshConversations = useCallback(async () => {
    if (!session) return;
    try {
      setConversations(await listConversations(session.userId));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to load conversations');
    }
  }, [session]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    if (!session || !conversationId) {
      setMessages([]);
      return;
    }
    localStorage.setItem('shinobu-conversation-id', conversationId);
    listMessages(conversationId, session.userId)
      .then(items => {
        const serverMessages = items.map(toChatMessage);
        setMessages(current => mergeServerMessages(current, serverMessages, streamingRef.current));
      })
      .catch(nextError => {
        setError(nextError instanceof Error ? nextError.message : 'Failed to load messages');
        localStorage.removeItem('shinobu-conversation-id');
        setConversationId(null);
      });
  }, [conversationId, session]);

  const selectedBackground = useMemo(
    () => backgrounds.find(item => item.id === petSettings.backgroundId) ?? backgrounds[0],
    [backgrounds, petSettings.backgroundId],
  );
  const selectedModel = useMemo(
    () => models.find(item => item.id === petSettings.modelId) ?? models[0],
    [models, petSettings.modelId],
  );

  const handleSession = (nextSession: AuthSession) => {
    saveSession(nextSession);
    setSession(nextSession);
    setError(null);
  };

  const logout = () => {
    saveSession(null);
    localStorage.removeItem('shinobu-conversation-id');
    setSession(null);
    setConversationId(null);
    setConversations([]);
    setMessages([]);
  };

  const startNewConversation = () => {
    setConversationId(null);
    localStorage.removeItem('shinobu-conversation-id');
    setMessages([]);
    setStatus('New conversation');
  };

  const notify = (message: string) => {
    setPetFeedback(message);
    window.setTimeout(() => setPetFeedback(current => current === message ? null : current), 1800);
    if (petSettings.reminderMode === 'sound') {
      const audio = new Audio();
      audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=';
      audio.play().catch(() => {});
    }
  };

  const updateAvatarEmotion = (message?: ApiMessage | null) => {
    if (message?.emotion) {
      setActiveEmotion(message.emotion);
    }
  };

  const sendText = async (text: string) => {
    if (!session || streaming) return;
    const content = text.trim();
    if (!content) return;
    setStreaming(true);
    setError(null);
    setStatus('Shinobu is replying...');

    let pendingId = `pending-${Date.now()}`;
    let streamConversationId = conversationId;
    let actualRouteMode = routeMode;
    try {
      await sendMessageStream({
        userId: session.userId,
        conversationId,
        content,
        routeMode,
        onEvent: event => {
          if (event.type === 'conversation') {
            streamConversationId = event.conversationId;
            actualRouteMode = event.routeMode;
            setConversationId(event.conversationId);
            localStorage.setItem('shinobu-conversation-id', event.conversationId);
            setMessages(current => {
              const exists = current.some(item => item.id === event.userMessage.id);
              return exists ? current : [...current, toChatMessage(event.userMessage)];
            });
            updateAvatarEmotion(event.userMessage);
            refreshConversations();
          }
          if (event.type === 'chunk') {
            setMessages(current => {
              const pending = current.find(item => item.id === pendingId);
              if (pending) {
                return current.map(item => item.id === pendingId ? { ...item, content: item.content + event.delta } : item);
              }
              return [
                ...current,
                {
                  id: pendingId,
                  conversation_id: streamConversationId || 'pending',
                  role: 'assistant',
                  content: event.delta,
                  route_mode: actualRouteMode,
                  created_at: new Date().toISOString(),
                  status: 'streaming',
                  local: true,
                },
              ];
            });
          }
          if (event.type === 'emotion') {
            setActiveEmotion(event.emotion);
          }
          if (event.type === 'progress') {
            setStatus(`${event.skillName}: ${event.message} (${Math.round(event.percent * 100)}%)`);
          }
          if (event.type === 'error') {
            setError(event.hint);
            setStatus('Action failed');
          }
          if (event.type === 'audio') {
            const segId = "seg-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
            setMessages(current => [
              ...current,
              {
                id: segId, conversation_id: streamConversationId || 'pending',
                role: 'assistant' as const, content: event.text,
                route_mode: actualRouteMode, created_at: new Date().toISOString(),
                status: 'streaming' as const, local: true,
              },
            ]);
            playBase64Audio(event.audio);
            if (event.emotion) setActiveEmotion(event.emotion);
            setSpokenLines(prev => [...prev, event.text]);
            setStatus(event.text);
          }
          if (event.type === 'done') {
            setMessages(current => {
              const serverMessages = event.assistantMessages.map(toChatMessage);
              const nonLocal = current.filter(item => !item.local);
              return [...nonLocal, ...serverMessages];
            });
            if (event.assistantMessages && event.assistantMessages.length > 0) {
              updateAvatarEmotion(event.assistantMessages[event.assistantMessages.length - 1]);
            }
            refreshConversations();
          }
        },
      });
      setStatus('Ready');
      notify('Reply complete');
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : 'Failed to send message';
      setError(message);
      setStatus('Send failed');
      setMessages(current => current.map(item => item.id === pendingId ? { ...item, status: 'failed' } : item));
    } finally {
      setStreaming(false);
    }
  };

  const sendVoiceInput = async (audio: Blob) => {
    if (!session || streaming) return;
    try {
      setError(null);
      setStatus('Transcribing voice...');
      const transcript = await transcribeSpeech(audio);
      await sendText(transcript.text);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Voice recognition failed');
      setStatus('Voice recognition failed');
    }
  };

  const handleAvatarTool = (tool: AvatarTool) => {
    setActiveTool(current => current === tool ? null : tool);
  };

  const handlePetInteraction = () => {
    if (!activeTool) return;
    const labels: Record<AvatarTool, string> = {
      lollipop: 'Candy offered',
      fist: 'Soft poke',
      hammer: 'Bonk',
    };
    notify(labels[activeTool]);
  };

  const handleScreenshot = async () => {
    try {
      await captureScreen();
      notify('Screenshot captured');
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Screen capture unavailable');
    }
  };

  const backgroundStyle = selectedBackground?.url
    ? { backgroundImage: `url("${selectedBackground.url}")` }
    : { background: selectedBackground?.gradient ?? 'linear-gradient(135deg, #dceefe, #f9e6ed)' };

  if (!session) {
    return (
      <main className="auth-screen" style={backgroundStyle}>
        <AuthPanel
          onRegister={registerUser}
          onLogin={(payload) => loginWithDeviceFlow({ ...payload, deviceName: navigator.userAgent.slice(0, 80) })}
          onSession={handleSession}
        />
      </main>
    );
  }

  return (
    <main className={sidebarCollapsed ? 'workspace sidebar-is-collapsed' : 'workspace'} style={backgroundStyle}>
      <aside className="app-sidebar" aria-label="ShinobuChat navigation">
        <header className="sidebar-header">
          <div className="sidebar-brand">
            <span className="sidebar-logo"><Sparkles size={18} /></span>
            <strong>ShinobuChat</strong>
          </div>
          <button
            type="button"
            className="icon-button"
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
            onClick={() => setSidebarCollapsed(current => !current)}
          >
            {sidebarCollapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}
          </button>
        </header>

        <nav className="sidebar-menu" aria-label="Primary">
          <button type="button" className="sidebar-item is-active" onClick={startNewConversation}>
            <MessageSquarePlus size={18} />
            <span>新对话</span>
          </button>
          <button type="button" className="sidebar-item" onClick={() => setSidebarPanel('history')}>
            <Search size={18} />
            <span>搜索聊天</span>
          </button>
          <button type="button" className="sidebar-item" onClick={() => setSidebarPanel('history')}>
            <History size={18} />
            <span>会话历史</span>
          </button>
          <button type="button" className="sidebar-item" onClick={() => setSidebarPanel('models')}>
            <UserRoundCog size={18} />
            <span>角色与模型</span>
          </button>
          <button type="button" className="sidebar-item" onClick={() => setSidebarPanel('scenes')}>
            <Music2 size={18} />
            <span>场景音乐</span>
          </button>
          <button type="button" className="sidebar-item" onClick={() => setSettingsOpen(true)}>
            <MoreHorizontal size={18} />
            <span>更多</span>
          </button>
        </nav>

        <div className="sidebar-panel">
          {sidebarPanel === 'history' ? (
            <ConversationList
              conversations={conversations}
              activeId={conversationId}
              onSelect={setConversationId}
            />
          ) : null}
          {sidebarPanel === 'models' ? (
            <div className="sidebar-card">
              <strong>角色与模型</strong>
              <span>{selectedModel?.name || '正在加载 Live2D 模型'}</span>
              <button type="button" className="sidebar-mini-action" onClick={() => setSettingsOpen(true)}>
                打开角色设置
              </button>
            </div>
          ) : null}
          {sidebarPanel === 'scenes' ? (
            <div className="sidebar-card">
              <strong>场景音乐</strong>
              <span>{selectedBackground?.name || '默认场景'} · {tracks.length} 首音乐</span>
              <button type="button" className="sidebar-mini-action" onClick={() => setSettingsOpen(true)}>
                调整舞台设置
              </button>
            </div>
          ) : null}
        </div>

        <footer className="sidebar-footer">
          <button type="button" className="sidebar-user" title={session.email}>
            <span>{(session.displayName || session.email || 'S').slice(0, 1).toUpperCase()}</span>
            <small>{session.displayName || session.email}</small>
          </button>
          <button type="button" className="icon-button" title="设置" onClick={() => setSettingsOpen(true)}>
            <Settings size={17} />
          </button>
        </footer>
      </aside>

      <section className="stage-zone">
        <Live2DStage
          model={selectedModel}
          settings={petSettings}
          activeEmotion={activeEmotion}
          activeTool={activeTool}
          onSettingsChange={setPetSettings}
          onInteract={handlePetInteraction}
          onLipSyncReady={setLipSyncRef}
        />
        <PetTaskbar
          activeTool={activeTool}
          onToolSelect={handleAvatarTool}
          onOpenSettings={() => setSettingsOpen(true)}
          onScreenshot={handleScreenshot}
        />
        {settingsOpen ? (
          <>
            <PetSettingsPanel
              settings={petSettings}
              models={models}
              backgrounds={backgrounds}
              onChange={setPetSettings}
              onRefreshModels={() => {
                reloadAssets().catch(nextError => {
                  setError(nextError instanceof Error ? nextError.message : 'Failed to refresh assets');
                });
              }}
              onClose={() => setSettingsOpen(false)}
            />
            <CharacterEditor userId={session.userId} />
          </>
        ) : null}
        {spokenLines.length > 0 ? (
          <div className="spoken-subtitle">
            {spokenLines.map((line, i) => (
              <p key={i} className={i === spokenLines.length - 1 ? 'is-active' : ''}>{line}</p>
            ))}
          </div>
        ) : null}
        {petFeedback ? <div className="pet-feedback">{petFeedback}</div> : null}
        <MusicPlayer tracks={tracks} />
      </section>

      <aside className="chat-shell" aria-label="Shinobu chat">
        <header className="chat-header">
          <div className="chat-title">
            <span className="chat-avatar"><Bot size={20} /></span>
            <div>
              <h1>Shinobu</h1>
              <p><span className="online-dot" />在线 · {status}</p>
            </div>
          </div>
          <div className="chat-header-actions">
            <button type="button" title="Refresh conversations" onClick={refreshConversations}><RefreshCw size={16} /></button>
            <button type="button" title="Toggle sidebar" onClick={() => setSidebarCollapsed(current => !current)}><PanelLeft size={16} /></button>
            <button type="button" title="Log out" onClick={logout}><LogOut size={16} /></button>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <section className="conversation-pane">
          <MessageList messages={messages} />
          <Composer
            disabled={streaming}
            routeMode={routeMode}
            galgameMode={galgameMode}
            onRouteModeChange={setRouteMode}
            onGalgameModeChange={setGalgameMode}
            onSubmit={sendText}
            onVoiceInput={sendVoiceInput}
          />
        </section>
      </aside>
    </main>
  );
}
