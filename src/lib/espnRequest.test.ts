import { describe, expect, it } from 'vitest';
import { ESPN_REQUEST_HEADERS } from './espnRequest';


describe('ESPN request headers', () => {
  it('does not send a browser user-agent from the server', () => {
    expect(ESPN_REQUEST_HEADERS).not.toHaveProperty('user-agent');
  });
});
