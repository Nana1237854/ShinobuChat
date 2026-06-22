import type { VisionAnalyzeResponse } from '../types';
import { requestJson } from './http';

export function analyzeImage(
  accessToken: string,
  file: File,
  question?: string | null,
): Promise<VisionAnalyzeResponse> {
  const body = new FormData();
  body.append('file', file);
  if (question) {
    body.append('question', question);
  }
  return requestJson<VisionAnalyzeResponse>('/vision/analyze', {
    method: 'POST',
    accessToken,
    body,
    json: false,
  });
}
