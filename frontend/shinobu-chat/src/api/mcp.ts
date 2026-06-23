import { requestJson } from './http';

export interface McpStatus {
  enabled: boolean;
  available: boolean;
  safe_tools: string[];
  blocked_tools: string[];
  default_user_id: string;
  message: string;
}

export function getMcpStatus(accessToken: string): Promise<McpStatus> {
  return requestJson<McpStatus>('/mcp/status', { accessToken });
}

export function patchMcpSettings(
  accessToken: string,
  data: { enabled?: boolean },
): Promise<McpStatus> {
  return requestJson<McpStatus>('/mcp/settings', {
    method: 'PATCH',
    accessToken,
    body: data,
  });
}
