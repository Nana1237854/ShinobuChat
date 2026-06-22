const API_BASE = '/api/v1';

export class ApiRequestError extends Error {
  status: number;
  detail: string;
  payload: unknown;

  constructor(status: number, detail: string, payload: unknown) {
    super(detail);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }
}

type Primitive = string | number | boolean;

type QueryValue = Primitive | null | undefined;

type JsonBody = Record<string, unknown>;

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  accessToken?: string;
  body?: BodyInit | JsonBody | null;
  headers?: HeadersInit;
  json?: boolean;
  query?: Record<string, QueryValue>;
};

function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const basePath = path.startsWith('/') ? path : `/${path}`;
  if (!query) return `${API_BASE}${basePath}`;

  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === '') continue;
    params.set(key, String(value));
  }

  const queryString = params.toString();
  return queryString ? `${API_BASE}${basePath}?${queryString}` : `${API_BASE}${basePath}`;
}

function buildHeaders(
  accessToken?: string,
  headers?: HeadersInit,
  json = true,
): Headers {
  const nextHeaders = new Headers(headers);
  if (json && !nextHeaders.has('Content-Type')) {
    nextHeaders.set('Content-Type', 'application/json');
  }
  if (accessToken && !nextHeaders.has('Authorization')) {
    nextHeaders.set('Authorization', `Bearer ${accessToken}`);
  }
  return nextHeaders;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('Content-Type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in payload
      ? String(payload.detail)
      : response.statusText || 'Request failed';
    throw new ApiRequestError(response.status, detail, payload);
  }

  return payload as T;
}

function toRequestBody(body: RequestOptions['body'], json: boolean): BodyInit | undefined {
  if (body == null) return undefined;
  if (!json || body instanceof FormData || typeof body === 'string') {
    return body as BodyInit;
  }
  return JSON.stringify(body);
}

export async function requestJson<T>(
  path: string,
  {
    method = 'GET',
    accessToken,
    body,
    headers,
    json = true,
    query,
  }: RequestOptions = {},
): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    method,
    headers: buildHeaders(accessToken, headers, json && !(body instanceof FormData)),
    body: toRequestBody(body, json),
  });

  return parseResponse<T>(response);
}

export async function requestVoid(
  path: string,
  options: RequestOptions = {},
): Promise<void> {
  await requestJson<void>(path, options);
}
