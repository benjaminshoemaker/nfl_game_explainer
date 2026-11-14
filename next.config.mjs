/** @type {import('next').NextConfig} */
const nextConfig = {
  skipTrailingSlashRedirect: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'a.espncdn.com',
      },
    ],
  },
  async redirects() {
    return [{ source: '/prediction-results', destination: '/power-rankings/prediction-results', permanent: true }];
  },
  async rewrites() {
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;
    const analytics = host ? [
      { source: '/ingest/static/:path*', destination: `${host.replace('.i.', '-assets.i.')}/static/:path*` },
      { source: '/ingest/:path*', destination: `${host}/:path*` },
    ] : [];
    const teamPages = ['/teams', '/teams/:team', '/power-rankings', '/power-rankings/prediction-results', '/team-methodology']
      .map((source) => ({ source, destination: '/team-seasons.html' }));
    // Only proxy to local Python server in development
    if (process.env.NODE_ENV === 'development') {
      return [
        ...analytics,
        ...teamPages,
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*',
        },
      ];
    }
    return [...analytics, ...teamPages];
  },
};

export default nextConfig;
