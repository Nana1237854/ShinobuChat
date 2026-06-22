import type { ConfigListResponse, ConfigUpdateRequest } from '../types';
import { requestJson } from './http';

export function getUserConfig(accessToken: string): Promise<ConfigListResponse> {
  return requestJson<ConfigListResponse>('/config/user/me', { accessToken });
}

export function updateUserConfig(
  accessToken: string,
  fields: ConfigUpdateRequest,
): Promise<ConfigListResponse> {
  return requestJson<ConfigListResponse>('/config/user/me', {
    method: 'PATCH',
    accessToken,
    body: fields,
  });
}

export function resetUserConfig(accessToken: string): Promise<ConfigListResponse> {
  return requestJson<ConfigListResponse>('/config/user/me/reset', {
    method: 'PUT',
    accessToken,
  });
}
