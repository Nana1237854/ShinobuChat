import clsx from 'clsx';
import type { Conversation } from '../types';

type ConversationListProps = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
};

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function ConversationList({ conversations, activeId, onSelect }: ConversationListProps) {
  return (
    <nav className="conversation-list" aria-label="Conversations">
      <div className="conversation-list-title">会话</div>
      {conversations.length === 0 ? (
        <div className="empty-note">发送第一条消息后会自动创建会话。</div>
      ) : conversations.map(item => (
        <button
          key={item.id}
          type="button"
          className={clsx('conversation-item', item.id === activeId && 'is-active')}
          onClick={() => onSelect(item.id)}
        >
          <span>{item.title || 'New conversation'}</span>
          <small>{item.summary || formatDate(item.updated_at)}</small>
        </button>
      ))}
    </nav>
  );
}
