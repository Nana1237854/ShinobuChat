import type { GoalCheckin, GoalCreateRequest, GoalItem, GoalUpdateRequest } from '../types';
import { requestJson } from './http';

export function listGoals(
  accessToken: string,
  options: { status?: string; include_completed?: boolean } = {},
): Promise<GoalItem[]> {
  return requestJson<GoalItem[]>('/goals', {
    accessToken,
    query: options,
  });
}

export function createGoal(
  accessToken: string,
  payload: GoalCreateRequest,
): Promise<GoalItem> {
  return requestJson<GoalItem>('/goals', {
    method: 'POST',
    accessToken,
    body: payload,
  });
}

export function updateGoal(
  accessToken: string,
  goalId: string,
  payload: GoalUpdateRequest,
): Promise<GoalItem> {
  return requestJson<GoalItem>(`/goals/${encodeURIComponent(goalId)}`, {
    method: 'PATCH',
    accessToken,
    body: payload,
  });
}

export function checkinGoal(
  accessToken: string,
  goalId: string,
): Promise<GoalCheckin> {
  return requestJson<GoalCheckin>(`/goals/${encodeURIComponent(goalId)}/checkin`, {
    method: 'POST',
    accessToken,
  });
}
