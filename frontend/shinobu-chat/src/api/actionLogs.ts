import { requestJson } from './http';

export interface ActionLogEntry {
  id: string;
  user_id: string;
  conversation_id: string | null;
  action_type: string;
  target: string;
  status: string;
  message: string | null;
  error_detail: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface BrowserActionLogEntry {
  id: string;
  user_id: string;
  action_type: string;
  target_url: string | null;
  status: string;
  message: string | null;
  error_detail: string | null;
  payload_json: Record<string, unknown> | null;
  created_at: string;
  finished_at: string | null;
}

export function getLocalActionLogs(
  accessToken: string,
  params?: { action_type?: string; status?: string; limit?: number; offset?: number },
): Promise<{ logs: ActionLogEntry[] }> {
  return requestJson('/local-agent/actions/logs', {
    accessToken,
    query: params as Record<string, string>,
  });
}

export function getBrowserActionLogs(
  accessToken: string,
  params?: { action_type?: string; status?: string; limit?: number; offset?: number },
): Promise<{ logs: BrowserActionLogEntry[] }> {
  return requestJson('/browser/actions/logs', {
    accessToken,
    query: params as Record<string, string>,
  });
}
