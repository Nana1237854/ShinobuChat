import { requestJson } from './http';

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

export interface WebLink {
  text: string;
  href: string;
}

export interface BrowserReadResult {
  status: string;
  title: string;
  url: string;
  content: string;
  links: WebLink[];
  metadata: Record<string, unknown>;
  message: string;
}

export interface BrowserSummarizeResult {
  status: string;
  summary: string;
  key_points: string[];
  source_url: string;
  message: string;
}

export interface DownloadCandidate {
  text: string;
  href: string;
  domain: string;
  extension: string;
}

export interface ClassifiedDownload {
  text: string;
  href: string;
  domain: string;
  extension: string;
  risk_level: string;
  reasons: string[];
  suggested_action: string;
  requires_confirmation: boolean;
}

export function searchWeb(
  accessToken: string,
  query: string,
  maxResults: number = 5,
): Promise<{ status: string; results: SearchResult[]; message: string }> {
  return requestJson('/browser/search', {
    method: 'POST',
    accessToken,
    body: { query, max_results: maxResults },
  });
}

export function readWebPage(
  accessToken: string,
  url: string,
  maxChars: number = 10000,
): Promise<BrowserReadResult> {
  return requestJson('/browser/read', {
    method: 'POST',
    accessToken,
    body: { url, max_chars: maxChars },
  });
}

export function summarizeWebPage(
  accessToken: string,
  url: string,
  question: string = '',
  maxChars: number = 10000,
): Promise<BrowserSummarizeResult> {
  return requestJson('/browser/summarize', {
    method: 'POST',
    accessToken,
    body: { url, question, max_chars: maxChars },
  });
}

export function openUrl(
  accessToken: string,
  url: string,
): Promise<{ status: string; message: string }> {
  return requestJson('/browser/open-url', {
    method: 'POST',
    accessToken,
    body: { url },
  });
}

export function extractDownloadCandidates(
  accessToken: string,
  url: string,
): Promise<{ status: string; candidates: DownloadCandidate[]; message: string }> {
  return requestJson('/browser/download-candidates', {
    method: 'POST',
    accessToken,
    body: { url },
  });
}

export function classifyDownloads(
  accessToken: string,
  candidates: DownloadCandidate[],
): Promise<{ status: string; classified: ClassifiedDownload[]; message: string }> {
  return requestJson('/browser/classify-downloads', {
    method: 'POST',
    accessToken,
    body: { candidates },
  });
}
