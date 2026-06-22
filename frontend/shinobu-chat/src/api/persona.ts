import type { PersonaSettings, PersonaSettingsUpdateRequest } from '../types';
import { requestJson } from './http';

export function getPersonaSettings(accessToken: string): Promise<PersonaSettings> {
  return requestJson<PersonaSettings>('/persona/settings', { accessToken });
}

export function updatePersonaSettings(
  accessToken: string,
  settings: PersonaSettingsUpdateRequest,
): Promise<PersonaSettings> {
  return requestJson<PersonaSettings>('/persona/settings', {
    method: 'PUT',
    accessToken,
    body: settings,
  });
}
