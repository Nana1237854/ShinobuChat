import type { MarketSkill, SkillDetail, SkillInstallRequest, SkillSummary } from '../types';
import { requestJson, requestVoid } from './http';

export function listUserSkills(accessToken: string): Promise<SkillSummary[]> {
  return requestJson<SkillSummary[]>('/skills/user/me', { accessToken });
}

export function installSkillFromText(
  accessToken: string,
  content: string,
): Promise<SkillDetail> {
  const payload: SkillInstallRequest = {
    install_type: 'text',
    content,
  };

  return requestJson<SkillDetail>('/skills/user/me', {
    method: 'POST',
    accessToken,
    body: payload,
  });
}

export function getSkillDetail(
  accessToken: string,
  skillId: string,
): Promise<SkillDetail> {
  return requestJson<SkillDetail>(`/skills/user/me/${encodeURIComponent(skillId)}`, {
    accessToken,
  });
}

export function updateSkill(
  accessToken: string,
  skillId: string,
  content: string,
): Promise<SkillDetail> {
  return requestJson<SkillDetail>(`/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'PUT',
    accessToken,
    body: { content },
  });
}

export function deleteSkill(accessToken: string, skillId: string): Promise<void> {
  return requestVoid(`/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
    accessToken,
  });
}

export function toggleSkill(
  accessToken: string,
  skillId: string,
  enabled: boolean,
): Promise<SkillSummary> {
  return requestJson<SkillSummary>(`/skills/user/me/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    accessToken,
    body: { enabled },
  });
}

export function listSkillMarket(): Promise<MarketSkill[]> {
  return requestJson<MarketSkill[]>('/skills/market');
}

export function installMarketSkill(
  accessToken: string,
  name: string,
): Promise<SkillDetail> {
  return requestJson<SkillDetail>(`/skills/market/${encodeURIComponent(name)}/install`, {
    method: 'POST',
    accessToken,
  });
}
