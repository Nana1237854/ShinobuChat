import type {
  ApiMessage,
  AuthSession,
  CharacterCard,
  CharacterCardOverride,
  Conversation,
  MarketSkill,
  RouteMode,
  StreamEvent,
  UserConfigResponse,
  UserSkill,
} from '../types';
import { decodeJwtSubject } from './auth';
import { consumeSseStream } from './sse';

const API_BASE = '/api/v1';

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : response.statusText;
    throw new Error(detail || 'Request failed');
  }
  return data as T;
}

export async function registerUser(payload: {
  email: string;
  password: string;
  display_name?: string;
}) {
  const response = await fetch(`${API_BASE}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse<{ id: string; email: string; display_name?: string | null }>(response);
}

export async function loginWithDeviceFlow(payload: {
  email: string;
  password: string;
  deviceName: string;
  deviceType?: string;
}): Promise<AuthSession> {
  const authorizeResponse = await fetch(`${API_BASE}/auth/device/authorize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
      device_name: payload.deviceName,
      device_type: payload.deviceType ?? 'browser',
    }),
  });
  const authorization = await parseJsonResponse<{ device_code: string }>(authorizeResponse);

  const tokenResponse = await fetch(`${API_BASE}/auth/device/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_code: authorization.device_code }),
  });
  const token = await parseJsonResponse<{ access_token: string }>(tokenResponse);

  return {
    accessToken: token.access_token,
    userId: decodeJwtSubject(token.access_token),
    email: payload.email,
  };
}

export async function listConversations(userId: string): Promise<Conversation[]> {
  const response = await fetch(`${API_BASE}/conversations/user/${encodeURIComponent(userId)}`);
  return parseJsonResponse<Conversation[]>(response);
}

export async function listMessages(conversationId: string, userId: string): Promise<ApiMessage[]> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(`${API_BASE}/conversations/${encodeURIComponent(conversationId)}/messages?${params}`);
  return parseJsonResponse<ApiMessage[]>(response);
}

export async function fetchCharacterCard(userId: string): Promise<CharacterCard> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(`${API_BASE}/characters/active?${params}`);
  return parseJsonResponse<CharacterCard>(response);
}

export async function updateCharacterCard(
  userId: string,
  override: CharacterCardOverride,
): Promise<CharacterCard> {
  const params = new URLSearchParams({ user_id: userId });
  const response = await fetch(`${API_BASE}/characters/active?${params}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(override),
  });
  return parseJsonResponse<CharacterCard>(response);
}

export async function sendMessageStream(payload: {
  userId: string;
  conversationId?: string | null;
  content: string;
  routeMode: RouteMode;
  onEvent: (event: StreamEvent) => void;
}) {
  const response = await fetch(`${API_BASE}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({
      user_id: payload.userId,
      conversation_id: payload.conversationId || null,
      content: payload.content,
      route_mode: payload.routeMode,
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : 'Message request failed';
    throw new Error(detail);
  }

  await consumeSseStream(response, payload.onEvent);
}

export async function transcribeSpeech(audio: Blob): Promise<{ text: string; engine: string }> {
  const body = new FormData();
  body.append('file', audio, `speech.${audio.type.includes('webm') ? 'webm' : 'wav'}`);
  const response = await fetch(`${API_BASE}/voice/asr`, {
    method: 'POST',
    body,
  });
  return parseJsonResponse<{ text: string; engine: string }>(response);
}

export async function synthesizeSpeech(payload: {
  text: string;
  emotion?: string | null;
  context?: string[];
}): Promise<{ audio: Blob; emotion: string | null; reference: string | null }> {
  const response = await fetch(`${API_BASE}/voice/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: payload.text,
      emotion: payload.emotion || null,
      context: payload.context ?? [],
    }),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : 'Voice synthesis failed';
    throw new Error(detail);
  }

  return {
    audio: await response.blob(),
    emotion: response.headers.get('X-Shinobu-Voice-Emotion'),
    reference: response.headers.get('X-Shinobu-Voice-Reference'),
  };
}


function authorizedHeaders(accessToken: string, json = true): HeadersInit {
  return {
    ...(json ? { 'Content-Type': 'application/json' } : {}),
    Authorization: `Bearer ${accessToken}`,
  };
}

export async function fetchUserConfig(accessToken: string): Promise<UserConfigResponse> {
  const response = await fetch(`${API_BASE}/config/user/me`, {
    headers: authorizedHeaders(accessToken, false),
  });
  return parseJsonResponse<UserConfigResponse>(response);
}

export async function updateUserConfig(
  accessToken: string,
  values: Record<string, string | number | boolean | null>,
): Promise<UserConfigResponse> {
  const response = await fetch(`${API_BASE}/config/user/me`, {
    method: 'PATCH',
    headers: authorizedHeaders(accessToken),
    body: JSON.stringify(values),
  });
  return parseJsonResponse<UserConfigResponse>(response);
}

export async function resetUserConfig(accessToken: string): Promise<UserConfigResponse> {
  const response = await fetch(`${API_BASE}/config/user/me/reset`, {
    method: 'PUT',
    headers: authorizedHeaders(accessToken),
  });
  return parseJsonResponse<UserConfigResponse>(response);
}

export async function listUserSkills(accessToken: string): Promise<UserSkill[]> {
  const response = await fetch(`${API_BASE}/skills/user/me`, {
    headers: authorizedHeaders(accessToken, false),
  });
  return parseJsonResponse<UserSkill[]>(response);
}

export async function getUserSkill(accessToken: string, skillId: string): Promise<UserSkill> {
  const response = await fetch(`${API_BASE}/skills/user/me/${encodeURIComponent(skillId)}`, {
    headers: authorizedHeaders(accessToken, false),
  });
  return parseJsonResponse<UserSkill>(response);
}

export async function installUserSkill(accessToken: string, content: string): Promise<UserSkill> {
  const response = await fetch(`${API_BASE}/skills/user/me`, {
    method: 'POST',
    headers: authorizedHeaders(accessToken),
    body: JSON.stringify({ install_type: 'text', content }),
  });
  return parseJsonResponse<UserSkill>(response);
}

export async function updateUserSkill(
  accessToken: string,
  skillId: string,
  content: string,
): Promise<UserSkill> {
  const response = await fetch(`${API_BASE}/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'PUT',
    headers: authorizedHeaders(accessToken),
    body: JSON.stringify({ content }),
  });
  return parseJsonResponse<UserSkill>(response);
}

export async function setUserSkillEnabled(
  accessToken: string,
  skillId: string,
  enabled: boolean,
): Promise<UserSkill> {
  const response = await fetch(`${API_BASE}/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    headers: authorizedHeaders(accessToken),
    body: JSON.stringify({ enabled }),
  });
  return parseJsonResponse<UserSkill>(response);
}

export async function deleteUserSkill(accessToken: string, skillId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
    headers: authorizedHeaders(accessToken, false),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = data && typeof data === 'object' && 'detail' in data ? String(data.detail) : 'Delete failed';
    throw new Error(detail);
  }
}

export async function listMarketSkills(): Promise<MarketSkill[]> {
  const response = await fetch(`${API_BASE}/skills/market`);
  return parseJsonResponse<MarketSkill[]>(response);
}

export async function installMarketSkill(accessToken: string, name: string): Promise<UserSkill> {
  const response = await fetch(`${API_BASE}/skills/market/${encodeURIComponent(name)}/install`, {
    method: 'POST',
    headers: authorizedHeaders(accessToken),
  });
  return parseJsonResponse<UserSkill>(response);
}
