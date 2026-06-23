import type {
  LocalApp,
  LocalAppCreateParams,
  LocalAppOpenParams,
  LocalAppTestResult,
  LocalAppUpdateParams,
} from '../types';
import { requestJson, requestVoid } from './http';

export function listLocalApps(accessToken: string): Promise<LocalApp[]> {
  return requestJson<LocalApp[]>('/local-apps', { accessToken });
}

export function createLocalApp(
  accessToken: string,
  data: LocalAppCreateParams,
): Promise<LocalApp> {
  return requestJson<LocalApp>('/local-apps', {
    method: 'POST',
    accessToken,
    body: data as unknown as Record<string, unknown>,
  });
}

export function updateLocalApp(
  accessToken: string,
  appId: string,
  data: LocalAppUpdateParams,
): Promise<LocalApp> {
  return requestJson<LocalApp>(`/local-apps/${encodeURIComponent(appId)}`, {
    method: 'PATCH',
    accessToken,
    body: data as unknown as Record<string, unknown>,
  });
}

export function deleteLocalApp(accessToken: string, appId: string): Promise<void> {
  return requestVoid(`/local-apps/${encodeURIComponent(appId)}`, {
    method: 'DELETE',
    accessToken,
  });
}

export function testLocalApp(
  accessToken: string,
  appId: string,
): Promise<LocalAppTestResult> {
  return requestJson<LocalAppTestResult>(
    `/local-apps/${encodeURIComponent(appId)}/test`,
    {
      method: 'POST',
      accessToken,
    },
  );
}

export function openLocalApp(
  accessToken: string,
  params: LocalAppOpenParams,
): Promise<{ success: boolean; message: string; task_id?: string }> {
  return requestJson<{ success: boolean; message: string; task_id?: string }>(
    '/local-apps/open',
    {
      method: 'POST',
      accessToken,
      body: params as unknown as Record<string, unknown>,
    },
  );
}
