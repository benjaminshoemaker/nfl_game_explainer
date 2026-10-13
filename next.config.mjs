/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'a.espncdn.com',
      },
    ],
  },
  async rewrites() {
    const teamPages = ['/teams', '/teams/:team', '/power-rankings', '/prediction-results', '/team-methodology']
      .map((source) => ({ source, destination: '/team-seasons.html' }));
    // Only proxy to local Python server in development
    if (process.env.NODE_ENV === 'development') {
      return [
        ...teamPages,
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*',
        },
      ];
    }
    return teamPages;
  },
};

export default nextConfig;
