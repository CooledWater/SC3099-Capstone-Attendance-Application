/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    const backend = (process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    // Next normalizes browser URLs without a trailing slash. Forward collection
    // routes to FastAPI's canonical URL directly to avoid external HTTP redirects.
    const dashboard = (process.env.DASHBOARD_INTERNAL_URL || 'http://127.0.0.1:8501').replace(/\/$/, '');
    return [
      { source: '/dashboard', destination: `${dashboard}/dashboard/` },
      { source: '/dashboard/:path*', destination: `${dashboard}/dashboard/:path*` },
      { source: '/api/v1/checkins', destination: `${backend}/api/v1/checkins/` },
      { source: '/api/v1/sessions', destination: `${backend}/api/v1/sessions/` },
      { source: '/api/v1/:path*', destination: `${backend}/api/v1/:path*` },
    ];
  },
  async headers() {
    return ['/sw.js', '/sw-precache.js'].map(source => ({ source, headers: [{ key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' }] }));
  },
}

module.exports = nextConfig
