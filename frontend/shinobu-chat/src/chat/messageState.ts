import type { ChatMessage } from '../types';

export function mergeServerMessages(
  current: ChatMessage[],
  incoming: ChatMessage[],
  preserveLocal: boolean,
): ChatMessage[] {
  if (!preserveLocal) return incoming;

  const incomingIds = new Set(incoming.map(message => message.id));
  const localMessages = current.filter(message => {
    const isLocalInFlight = message.local || message.status === 'streaming' || message.status === 'sending';
    return isLocalInFlight && !incomingIds.has(message.id);
  });

  return [...incoming, ...localMessages];
}

export function completeAssistantMessage(
  current: ChatMessage[],
  pendingId: string,
  assistantMessage: ChatMessage,
): ChatMessage[] {
  const next = current.filter(message => {
    if (message.id === pendingId || message.id === assistantMessage.id) return false;

    const sameConversation =
      message.conversation_id === assistantMessage.conversation_id ||
      message.conversation_id === 'pending';
    const isStreamingAssistant =
      message.role === 'assistant' &&
      (message.local || message.status === 'streaming') &&
      sameConversation;

    return !isStreamingAssistant;
  });

  return [...next, assistantMessage];
}
