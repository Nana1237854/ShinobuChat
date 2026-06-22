import type { MemoryContext, MemorySearchResult, MemoryTimelineItem } from '../types';
import { requestJson } from './http';

export function getMemoryTimeline(
  accessToken: string,
  options: { limit?: number; offset?: number } = {},
): Promise<MemoryTimelineItem[]> {
  return requestJson<MemoryTimelineItem[]>('/memories/timeline', {
    accessToken,
    query: options,
  });
}

export function searchMemories(
  accessToken: string,
  q: string,
  options: { limit?: number } = {},
): Promise<MemorySearchResult[]> {
  return requestJson<MemorySearchResult[]>('/memories/search', {
    accessToken,
    query: { q, limit: options.limit },
  });
}

export function getMemoryContext(
  accessToken: string,
  memoryId: string,
  options: { window?: number } = {},
): Promise<MemoryContext> {
  return requestJson<MemoryContext>(`/memories/${encodeURIComponent(memoryId)}/context`, {
    accessToken,
    query: options,
  });
}
