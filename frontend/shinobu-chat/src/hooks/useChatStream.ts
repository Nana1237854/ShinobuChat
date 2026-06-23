import { useCallback, useEffect, useRef, useState } from 'react';
import { sendMessageStream } from '../api/client';
import type {
  ApiMessage,
  AuthSession,
  ChatMessage,
  RouteMode,
  StreamEvent,
} from '../types';

export interface UseChatStreamDeps {
  session: AuthSession | null;
  conversationId: string | null;
  routeMode: RouteMode;
  pendingVisionContext: string | null;
  setConversationId: (id: string) => void;
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  setError: (error: string | null) => void;
  setStatus: (status: string) => void;
  setPendingVisionContext: (ctx: string | null) => void;
  setPendingAction: (action: any) => void;
  setActiveEmotion: (emotion: string | null) => void;
  setActionLogs: React.Dispatch<React.SetStateAction<any[]>>;
  setActionPanelExpanded: (expanded: boolean) => void;
  refreshConversations: () => void;
  notify: (message: string) => void;
  applyEmotionState: (state: any) => void;
  toChatMessage: (msg: ApiMessage) => ChatMessage;
}

export function useChatStream(deps: UseChatStreamDeps) {
  const [streaming, setStreaming] = useState(false);
  const streamingRef = useRef(streaming);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  const sendText = useCallback(async (text: string) => {
    if (!deps.session || streamingRef.current) return;

    const content = text.trim();
    if (!content) return;

    setStreaming(true);
    deps.setError(null);
    deps.setStatus('Shinobu is replying...');

    let chunkBuffer = '';
    let rafPending = false;
    const pendingId = `pending-${Date.now()}`;
    let streamConversationId = deps.conversationId;
    let actualRouteMode = deps.routeMode;

    try {
      const visionCtx = deps.pendingVisionContext;
      if (visionCtx) deps.setPendingVisionContext(null);

      await sendMessageStream({
        userId: deps.session.userId,
        conversationId: deps.conversationId,
        content,
        routeMode: deps.routeMode,
        accessToken: deps.session.accessToken,
        visionContext: visionCtx,
        onEvent: (event: StreamEvent) => {
          switch (event.type) {
            case 'conversation':
              streamConversationId = event.conversationId;
              actualRouteMode = event.routeMode;
              deps.setConversationId(event.conversationId);
              localStorage.setItem('shinobu-conversation-id', event.conversationId);
              deps.setMessages(current => {
                const exists = current.some(item => item.id === event.userMessage.id);
                return exists ? current : [...current, deps.toChatMessage(event.userMessage)];
              });
              deps.refreshConversations();
              break;

            case 'chunk':
              chunkBuffer += event.delta;
              if (!rafPending) {
                rafPending = true;
                requestAnimationFrame(() => {
                  const delta = chunkBuffer;
                  chunkBuffer = '';
                  rafPending = false;
                  deps.setMessages(current => {
                    const pending = current.find(item => item.id === pendingId);
                    if (pending) {
                      return current.map(item =>
                        item.id === pendingId ? { ...item, content: item.content + delta } : item,
                      );
                    }
                    return [
                      ...current,
                      {
                        id: pendingId,
                        conversation_id: streamConversationId || 'pending',
                        role: 'assistant',
                        content: delta,
                        route_mode: actualRouteMode,
                        created_at: new Date().toISOString(),
                        status: 'streaming',
                        local: true,
                      },
                    ];
                  });
                });
              }
              break;

            case 'progress':
              deps.setStatus(`${event.skillName}: ${event.message} (${Math.round(event.percent * 100)}%)`);
              break;

            case 'emotion':
              deps.setActiveEmotion(event.emotion);
              if (event.emotionState) {
                deps.applyEmotionState(event.emotionState);
              }
              break;

            case 'audio':
              deps.setMessages(current => [
                ...current,
                {
                  id: `seg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                  conversation_id: streamConversationId || 'pending',
                  role: 'assistant' as const,
                  content: event.text,
                  route_mode: actualRouteMode,
                  created_at: new Date().toISOString(),
                  status: 'streaming' as const,
                  local: true,
                },
              ]);
              deps.setStatus(event.text);
              if (event.emotion) deps.setActiveEmotion(event.emotion);
              break;

            case 'action':
              deps.setActionLogs(current => {
                const wasEmpty = current.length === 0;
                const next = [
                  ...current,
                  {
                    timestamp: event.action.timestamp || new Date().toISOString(),
                    message: event.action.message,
                    status: event.action.status,
                    appKey: event.action.app_key ?? null,
                    displayName: event.action.display_name ?? null,
                  },
                ];
                // Only auto-expand on first log; manual collapse is respected thereafter
                if (wasEmpty) deps.setActionPanelExpanded(true);
                return next;
              });
              deps.setStatus(event.action.message);
              break;

            case 'pending_action':
              deps.setPendingAction(event.pendingAction);
              deps.setStatus(`等待确认: ${event.pendingAction.description || event.pendingAction.display_name || ''}`);
              break;

            case 'error':
              deps.setError(event.hint);
              deps.setStatus('AI service unavailable');
              break;

            case 'done':
              deps.setMessages(current => {
                const serverMessages = event.assistantMessages.map(deps.toChatMessage);
                const nonLocal = current.filter(item => !item.local);
                return [...nonLocal, ...serverMessages];
              });
              if (event.pendingAction) {
                deps.setPendingAction(event.pendingAction);
              }
              deps.refreshConversations();
              break;
          }
        },
      });

      deps.setStatus('Ready');
      deps.notify('Reply complete');
    } catch (err) {
      deps.setError(err instanceof Error ? err.message : 'Failed to send message');
      deps.setStatus('Send failed');
    } finally {
      setStreaming(false);
    }
  }, [deps]);

  return { streaming, streamingRef, sendText };
}
