import { requestJson } from './http';

export interface LocalAgentSettings {
  local_launcher_enabled: boolean;
  browser_reader_enabled: boolean;
  browser_automation_enabled: boolean;
  mcp_enabled: boolean;
  allow_direct_open_music: boolean;
  allow_direct_open_browser: boolean;
  require_confirm_for_executable: boolean;
  require_confirm_for_unknown_url: boolean;
}

export type LocalAgentSettingsPatch = Partial<LocalAgentSettings>;

export function getLocalAgentSettings(accessToken: string): Promise<LocalAgentSettings> {
  return requestJson<LocalAgentSettings>('/local-agent/settings', { accessToken });
}

export function patchLocalAgentSettings(
  accessToken: string,
  patch: LocalAgentSettingsPatch,
): Promise<LocalAgentSettings> {
  return requestJson<LocalAgentSettings>('/local-agent/settings', {
    method: 'PATCH',
    accessToken,
    body: patch,
  });
}
