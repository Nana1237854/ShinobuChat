import type {
  DiaryDetail,
  DiaryGenerateRequest,
  DiaryGenerateResponse,
  DiaryItem,
} from '../types';
import { requestJson } from './http';

export function listDiaries(
  accessToken: string,
  params?: { limit?: number; offset?: number; mood?: string },
): Promise<DiaryItem[]> {
  return requestJson<DiaryItem[]>('/diaries', {
    accessToken,
    query: params as Record<string, string | number | undefined>,
  });
}

export function getDiaryByDate(
  accessToken: string,
  date: string,
): Promise<DiaryDetail> {
  return requestJson<DiaryDetail>(`/diaries/${encodeURIComponent(date)}`, {
    accessToken,
  });
}

export function generateDiary(
  accessToken: string,
  payload?: DiaryGenerateRequest,
): Promise<DiaryGenerateResponse> {
  return requestJson<DiaryGenerateResponse>('/diaries/generate', {
    method: 'POST',
    accessToken,
    body: payload ?? {},
  });
}
