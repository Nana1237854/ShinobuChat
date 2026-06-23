/** Operations API — Phase 3 Debug/Ops endpoints. */

import { requestJson } from './http';

export async function listJobRuns(accessToken: string) {
  return requestJson('/api/v1/debug/jobs/runs', { accessToken });
}

export async function listTaskRuns(accessToken: string) {
  return requestJson('/api/v1/debug/tasks', { accessToken });
}

export async function listSkillRuns(accessToken: string) {
  return requestJson('/api/v1/debug/skills/runs', { accessToken });
}

export async function listCapabilities(accessToken: string) {
  return requestJson('/api/v1/debug/capabilities', { accessToken });
}

export async function previewBehavior(accessToken: string, mode: string) {
  return requestJson('/api/v1/debug/behavior/preview', {
    accessToken,
    query: { mode },
  });
}
