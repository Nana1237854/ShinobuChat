import type { CharacterProfile } from '../types';
import { requestJson, requestVoid } from './http';

export type CharacterProfileCreateRequest = {
  name: string;
  persona: string;
  avatar_url?: string | null;
  color?: string | null;
};

export type CharacterProfileUpdateRequest = Partial<CharacterProfileCreateRequest>;

export function listCharacterProfiles(
  accessToken: string,
): Promise<CharacterProfile[]> {
  return requestJson<CharacterProfile[]>('/characters/profiles', { accessToken });
}

export function createCharacterProfile(
  accessToken: string,
  payload: CharacterProfileCreateRequest,
): Promise<CharacterProfile> {
  return requestJson<CharacterProfile>('/characters/profiles', {
    method: 'POST',
    accessToken,
    body: payload,
  });
}

export function updateCharacterProfile(
  accessToken: string,
  id: string,
  payload: CharacterProfileUpdateRequest,
): Promise<CharacterProfile> {
  return requestJson<CharacterProfile>(
    `/characters/profiles/${encodeURIComponent(id)}`,
    {
      method: 'PATCH',
      accessToken,
      body: payload,
    },
  );
}

export function deleteCharacterProfile(
  accessToken: string,
  id: string,
): Promise<void> {
  return requestVoid(`/characters/profiles/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    accessToken,
  });
}

export function updateConversationCharacters(
  accessToken: string,
  characterIds: string[],
): Promise<{ character_ids: string[] }> {
  return requestJson<{ character_ids: string[] }>('/characters/conversation', {
    method: 'PUT',
    accessToken,
    body: { character_ids: characterIds },
  });
}
