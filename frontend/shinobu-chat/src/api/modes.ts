import type { ModeSettings, ModeUpdateRequest } from '../types';
import { requestJson } from './http';

export function getConversationMode(accessToken: string): Promise<ModeSettings> {
  return requestJson<ModeSettings>('/modes/current', { accessToken });
}

export function updateConversationMode(
  accessToken: string,
  mode: ModeUpdateRequest['mode'],
): Promise<ModeSettings> {
  return requestJson<ModeSettings>('/modes/current', {
    method: 'PUT',
    accessToken,
    body: { mode },
  });
}
