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
          <h2>今天想和忍聊什么？</h2>
          <p>给 Shinobu 发消息，她会通过实时流式回复陪你继续。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list" ref={listRef}>
      {messages.map(message => (
        <article key={message.id} className={`message-row message-row-${message.role}`} data-status={message.status || ''}>
          <div className="message-avatar">{message.role === 'user' ? '你' : '忍'}</div>
          <div className="message-stack">
            <div className="message-meta">
              <span>{message.role === 'user' ? 'You' : 'Shinobu'}</span>
              <time>{formatTime(message.created_at)}</time>
              {message.status === 'streaming' ? <em>streaming</em> : null}
              {message.status === 'failed' ? <em>failed</em> : null}
            </div>
            <div className="message-bubble" aria-live={message.status === 'streaming' ? 'polite' : undefined}>
              <MessageContent content={message.content} streaming={message.status === 'streaming'} />
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
