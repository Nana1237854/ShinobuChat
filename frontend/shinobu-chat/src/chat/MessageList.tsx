import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import type { ChatMessage } from '../types';

type MessageListProps = {
  messages: ChatMessage[];
  onRetryVision?: () => void;
};

const MAX_VISIBLE = 200;

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function MessageContent({ content, streaming }: { content: string; streaming: boolean }) {
  const [displayedContent, setDisplayedContent] = useState(streaming ? '' : content);

  useEffect(() => {
    if (!streaming) {
      setDisplayedContent(content);
      return undefined;
    }

    let frameId = 0;
    const tick = () => {
      setDisplayedContent(current => {
        if (current.length >= content.length) return current;
        const remaining = content.length - current.length;
        const step = Math.max(1, Math.ceil(remaining / 8));
        return content.slice(0, current.length + step);
      });
      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [content, streaming]);

  return (
    <>
      <span className="message-content">{displayedContent}</span>
      {streaming ? <span className="typing-caret" aria-hidden="true" /> : null}
    </>
  );
}

const MessageRow = memo(function MessageRow({
  message,
  onRetryVision,
}: {
  message: ChatMessage;
  onRetryVision?: () => void;
}) {
  const isAux = message.is_auxiliary || false;
  const rowClass = [
    'message-row',
    `message-row-${message.role}`,
    isAux ? 'message-auxiliary' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const avatarClass = [
    'message-avatar',
    isAux && message.role !== 'user' ? 'message-avatar-auxiliary' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const getAvatarLetter = () => {
    if (message.role === 'user') return 'U';
    if (message.character_name && !message.character_name.startsWith('Vision')) return message.character_name.slice(0, 1);
    return 'S';
  };

  const getDisplayName = () => {
    if (message.role === 'user') return 'You';
    if (message.character_name) return message.character_name;
    return 'Shinobu';
  };

  return (
    <article
      className={rowClass}
      data-status={message.status || ''}
    >
      <div className={avatarClass}>{getAvatarLetter()}</div>
      <div className="message-stack">
        {message.character_name && message.role !== 'user' ? (
          <span
            className="message-character-name"
            style={{ color: message.character_color || undefined }}
          >
            {message.character_name}
          </span>
        ) : null}
        <div className="message-meta">
          <span>{getDisplayName()}</span>
          <time>{formatTime(message.created_at)}</time>
          {message.status === 'streaming' ? <em>streaming</em> : null}
          {message.status === 'failed' ? <em>failed</em> : null}
        </div>
        <div
          className="message-bubble"
          aria-live={
            message.status === 'streaming' ? 'polite' : undefined
          }
        >
          {message.image_preview_url ? (
            <div className="message-image-preview">
              <img src={message.image_preview_url} alt="上传的图片" />
            </div>
          ) : null}
          {message.status === 'vision-loading' ? (
            <div className="vision-loading">
              <span className="vision-spinner" />
              <span>{message.content}</span>
            </div>
          ) : message.status === 'vision-error' ? (
            <div className="vision-error-card">
              <p>{message.content}</p>
              {onRetryVision ? (
                <button type="button" className="vision-retry-btn" onClick={onRetryVision}>
                  <RefreshCw size={14} /> 重试
                </button>
              ) : null}
            </div>
          ) : (
            <MessageContent
              content={message.content}
              streaming={message.status === 'streaming'}
            />
          )}
        </div>
      </div>
    </article>
  );
});

export function MessageList({ messages, onRetryVision }: MessageListProps) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const userScrolledUp = useRef(false);
  const [showAll, setShowAll] = useState(false);

  const visibleMessages = useMemo(() => {
    if (showAll || messages.length <= MAX_VISIBLE) return messages;
    return messages.slice(messages.length - MAX_VISIBLE);
  }, [messages, showAll]);

  const hiddenCount = messages.length - visibleMessages.length;

  // Detect when user manually scrolls up
  const handleScroll = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    const distanceFromBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
    userScrolledUp.current = distanceFromBottom > 100;
  }, []);

  // Auto-scroll when new messages arrive (only if user is near bottom)
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;

    // Force scroll to bottom when a user message is being sent (status === 'sending')
    const lastMsg = messages[messages.length - 1];
    const isUserSending = lastMsg?.role === 'user' && lastMsg?.status === 'sending';

    if (isUserSending) {
      userScrolledUp.current = false;
    }

    if (!userScrolledUp.current) {
      requestAnimationFrame(() => {
        list.scrollTop = list.scrollHeight;
      });
    }
  }, [messages]);

  const scrollToBottom = useCallback(() => {
    const list = listRef.current;
    if (!list) return;
    userScrolledUp.current = false;
    list.scrollTop = list.scrollHeight;
  }, []);

  if (messages.length === 0) {
    return (
      <div className="message-list" ref={listRef}>
        <div className="welcome-card">
          <h2>今天想和 Shinobu 聊些什么？</h2>
          <p>发送消息，Shinobu 会通过实时回复陪伴在你身边。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={listRef} onScroll={handleScroll}>
      {hiddenCount > 0 ? (
        <button
          type="button"
          className="show-earlier-btn"
          onClick={() => setShowAll(true)}
        >
          显示更早的消息（{hiddenCount} 条）
        </button>
      ) : null}

      {visibleMessages.map(message => (
        <MessageRow key={message.id} message={message} onRetryVision={onRetryVision} />
      ))}

      {userScrolledUp.current ? (
        <button
          type="button"
          className="scroll-to-bottom"
          onClick={scrollToBottom}
          aria-label="滚动到底部"
        >
          ↓ 新消息
        </button>
      ) : null}
    </div>
  );
}
