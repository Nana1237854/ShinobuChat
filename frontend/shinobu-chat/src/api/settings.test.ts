import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchUserConfig,
  installUserSkill,
  updateUserConfig,
} from './client';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('settings API client', () => {
  it('sends bearer auth and consumes masked config values', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      fields: [
        { key: 'ai_api_key', value: 'sk-t••••alue', source: 'user', encrypted: true },
      ],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await fetchUserConfig('access-token');

    expect(response.fields[0].value).toBe('sk-t••••alue');
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/config/user/me', {
      headers: {
        Authorization: 'Bearer access-token',
      },
    });
  });

  it('patches only the values selected by the settings panel', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      fields: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await updateUserConfig('access-token', { ai_model: 'test-model' });

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(request.method).toBe('PATCH');
    expect(JSON.parse(String(request.body))).toEqual({ ai_model: 'test-model' });
  });

  it('installs pure SKILL.md content as text', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 'skill-id',
      name: 'test-skill',
      description: 'test',
      keywords: [],
      enabled: true,
      installed_from: 'text',
      source_url: null,
      content: '---',
      created_at: '2026-06-22T00:00:00Z',
      updated_at: '2026-06-22T00:00:00Z',
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await installUserSkill('access-token', '---\nname: test-skill\ndescription: test\n---\n');

    const request = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(request.body))).toMatchObject({
      install_type: 'text',
      content: expect.stringContaining('name: test-skill'),
    });
  });
});
