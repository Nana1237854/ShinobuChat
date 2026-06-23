import type { PendingAction } from '../types';
import { requestJson, requestVoid } from './http';

export function getActivePendingAction(
  accessToken: string,
  conversationId: string,
): Promise<PendingAction | null> {
  return requestJson<PendingAction | null>('/pending-actions/active', {
    accessToken,
    query: { conversation_id: conversationId },
  });
}

export function confirmPendingAction(
  accessToken: string,
  actionId: string,
): Promise<PendingAction> {
  return requestJson<PendingAction>(
    `/pending-actions/${encodeURIComponent(actionId)}/confirm`,
    { method: 'POST', accessToken },
  );
}

export function cancelPendingAction(
  accessToken: string,
  actionId: string,
): Promise<PendingAction> {
  return requestJson<PendingAction>(
    `/pending-actions/${encodeURIComponent(actionId)}/cancel`,
    { method: 'POST', accessToken },
  );
}
