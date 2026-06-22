import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChatMessage } from '../types';

type MessageListProps = {
  messages: ChatMessage[];
};

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

export function MessageList({ messages }: MessageListProps) {
  const listRef = useRef<HTMLDivElement | null>(null);
  const scrollKey = useMemo(() => {
    const lastMessage = messages[messages.length - 1];
    return lastMessage ? `${lastMessage.id}:${lastMessage.content.length}:${lastMessage.status ?? ''}` : 'empty';
  }, [messages]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;

    requestAnimationFrame(() => {
      list.scrollTop = list.scrollHeight;
    });
  }, [scrollKey]);

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

  const getAvatarLetter = (message: ChatMessage) => {
    if (message.role === 'user') return 'U';
    if (message.character_name) return message.character_name.slice(0, 1);
    return 'S';
  };

  const getDisplayName = (message: ChatMessage) => {
    if (message.role === 'user') return 'You';
    if (message.character_name) return message.character_name;
    return 'Shinobu';
  };

  return (
    <div className="message-list" ref={listRef}>
      {messages.map(message => {
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

        return (
          <article
            key={message.id}
            className={rowClass}
            data-status={message.status || ''}
          >
            <div className={avatarClass}>{getAvatarLetter(message)}</div>
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
                <span>{getDisplayName(message)}</span>
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
                <MessageContent
                  content={message.content}
                  streaming={message.status === 'streaming'}
                />
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
