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

export async function exportDiaries(
  accessToken: string,
  fromDate: string,
  toDate: string,
): Promise<{ text: string; filename: string }> {
  const baseUrl = '/api/v1';
  const params = new URLSearchParams({ from: fromDate, to: toDate, format: 'markdown' });
  const response = await fetch(`${baseUrl}/diaries/export?${params}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error((detail as { detail?: string }).detail || 'Export failed');
  }
  const text = await response.text();
  const disposition = response.headers.get('Content-Disposition') || '';
  const filenameMatch = disposition.match(/filename="?([^"]+)"?/);
  return { text, filename: filenameMatch?.[1] || 'diaries-export.md' };
}
