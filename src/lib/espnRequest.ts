/**
 * Headers for server-to-server ESPN requests.
 *
 * ESPN rejects browser User-Agents from server runtimes, so deliberately let
 * the runtime provide its own User-Agent.
 */
export const ESPN_REQUEST_HEADERS = {
  accept: 'application/json, text/plain, */*',
  'accept-language': 'en-US,en;q=0.9',
  referer: 'https://www.espn.com/',
  origin: 'https://www.espn.com',
};
