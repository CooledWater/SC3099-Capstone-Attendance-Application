import type { MetadataRoute } from 'next';
export default function manifest(): MetadataRoute.Manifest {
  return { name: 'SAIV Student Attendance', short_name: 'SAIV', description: 'Secure student attendance and identity verification', start_url: '/', display: 'standalone', background_color: '#f3f6f9', theme_color: '#123f73', icons: [{ src: '/icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' }] };
}
