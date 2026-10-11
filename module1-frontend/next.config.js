/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async headers() {
    return ['/sw.js', '/sw-precache.js'].map(source => ({ source, headers: [{ key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate' }] }));
  },
}

module.exports = nextConfig
