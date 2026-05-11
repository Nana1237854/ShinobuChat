import { decodeJwtSubject } from './auth';

function encodePayload(payload: object) {
  return btoa(JSON.stringify(payload)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

describe('decodeJwtSubject', () => {
  it('reads the sub claim from a JWT payload', () => {
    const token = `header.${encodePayload({ sub: 'user-123', exp: 9999999999 })}.signature`;
    expect(decodeJwtSubject(token)).toBe('user-123');
  });

  it('rejects malformed tokens', () => {
    expect(() => decodeJwtSubject('bad-token')).toThrow();
  });
});
