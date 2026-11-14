export const dynamic = 'force-dynamic';
export function GET() {
  const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
  const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;
  const testMode = process.env.ANALYTICS_TEST_MODE === '1' && process.env.VERCEL_ENV !== 'production';
  const enabled = process.env.VERCEL_ENV === 'production' || testMode;
  return Response.json(enabled && token && host ? { token, host, testMode } : {}, { headers: { 'Cache-Control': 'no-store' } });
}
