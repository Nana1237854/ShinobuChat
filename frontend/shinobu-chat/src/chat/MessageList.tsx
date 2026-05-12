import type { ChatMessage } from '../types';

type MessageListProps = {
  messages: ChatMessage[];
};

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="message-list">
        <div className="welcome-card">
          <h2>今天想和忍聊什么？</h2>
          <p>给 Shinobu 发消息，她会通过实时流式回复陪你继续。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
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
            <div className="message-bubble">{message.content}</div>
          </div>
        </article>
      ))}
    </div>
  );
}
