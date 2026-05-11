import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bot, LogOut, Plus, RefreshCw } from 'lucide-react';
import { AuthPanel } from './auth/AuthPanel';
import { ConversationList } from './chat/ConversationList';
import { MessageList } from './chat/MessageList';
import { Composer } from './chat/Composer';
import { Live2DStage } from './live2d/Live2DStage';
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
  const [status, setStatus] = useState('Ready');
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<Live2DModelItem[]>([]);
  const [backgrounds, setBackgrounds] = useState<BackgroundItem[]>([]);
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [petSettings, setPetSettings] = useState<PetSettings>(() => loadPetSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [activeTool, setActiveTool] = useState<AvatarTool | null>(null);
  const [petFeedback, setPetFeedback] = useState<string | null>(null);
  const [galgameMode, setGalgameMode] = useState(false);

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
      const modelId = current.modelId || nextModels[0]?.id;
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
    localStorage.setItem('shinobu-route-mode', routeMode);
  }, [routeMode]);

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
      .then(items => setMessages(items.map(toChatMessage)))
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

  const sendText = async (text: string) => {
    if (!session || streaming) return;
    const content = text.trim();
    if (!content) return;
    setStreaming(true);
    setError(null);
    setStatus('Shinobu is replying...');

    let pendingId = `pending-${Date.now()}`;
    try {
      await sendMessageStream({
        userId: session.userId,
        conversationId,
        content,
        routeMode,
        onEvent: event => {
          if (event.type === 'conversation') {
            setConversationId(event.payload.conversation_id);
            localStorage.setItem('shinobu-conversation-id', event.payload.conversation_id);
            setMessages(current => {
              const exists = current.some(item => item.id === event.payload.user_message.id);
              return exists ? current : [...current, toChatMessage(event.payload.user_message)];
            });
            refreshConversations();
          }
          if (event.type === 'chunk') {
            setMessages(current => {
              const pending = current.find(item => item.id === pendingId);
              if (pending) {
                return current.map(item => item.id === pendingId ? { ...item, content: item.content + event.payload.delta } : item);
              }
              return [
                ...current,
                {
                  id: pendingId,
                  conversation_id: conversationId || 'pending',
                  role: 'assistant',
                  content: event.payload.delta,
                  route_mode: routeMode,
                  created_at: new Date().toISOString(),
                  status: 'streaming',
                  local: true,
                },
              ];
            });
          }
          if (event.type === 'done') {
            setMessages(current => [
              ...current.filter(item => item.id !== pendingId),
              toChatMessage(event.payload.assistant_message),
            ]);
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
      pendingId = '';
      setStreaming(false);
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
    <main className="workspace" style={backgroundStyle}>
      <section className="stage-zone">
        <Live2DStage
          model={selectedModel}
          settings={petSettings}
          activeTool={activeTool}
          onSettingsChange={setPetSettings}
          onInteract={handlePetInteraction}
        />
        <PetTaskbar
          activeTool={activeTool}
          onToolSelect={handleAvatarTool}
          onOpenSettings={() => setSettingsOpen(true)}
          onScreenshot={handleScreenshot}
        />
        {settingsOpen ? (
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
        ) : null}
        {petFeedback ? <div className="pet-feedback">{petFeedback}</div> : null}
        <MusicPlayer tracks={tracks} />
      </section>

      <aside className="chat-shell" aria-label="Shinobu chat">
        <header className="chat-header">
          <div className="chat-title">
            <span className="chat-avatar"><Bot size={20} /></span>
            <div>
              <h1>ShinobuChat</h1>
              <p>{status}</p>
            </div>
          </div>
          <div className="chat-header-actions">
            <button type="button" title="Refresh conversations" onClick={refreshConversations}><RefreshCw size={16} /></button>
            <button type="button" title="New conversation" onClick={startNewConversation}><Plus size={16} /></button>
            <button type="button" title="Log out" onClick={logout}><LogOut size={16} /></button>
          </div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="chat-layout">
          <ConversationList
            conversations={conversations}
            activeId={conversationId}
            onSelect={setConversationId}
          />
          <section className="conversation-pane">
            <MessageList messages={messages} />
            <Composer
              disabled={streaming}
              routeMode={routeMode}
              galgameMode={galgameMode}
              onRouteModeChange={setRouteMode}
              onGalgameModeChange={setGalgameMode}
              onSubmit={sendText}
            />
          </section>
        </div>
      </aside>
    </main>
  );
}
