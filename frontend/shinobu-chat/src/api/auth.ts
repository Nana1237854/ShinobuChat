import { z } from 'zod';

const jwtPayloadSchema = z.object({
  sub: z.string().min(1),
  exp: z.number().optional(),
});

function base64UrlDecode(input: string): string {
  const normalized = input.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return atob(padded);
}

export function decodeJwtSubject(token: string): string {
  const [, payload] = token.split('.');
  if (!payload) {
    throw new Error('Invalid access token');
  }
  const parsed = jwtPayloadSchema.parse(JSON.parse(base64UrlDecode(payload)));
  return parsed.sub;
}
