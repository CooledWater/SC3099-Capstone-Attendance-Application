import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SAIV - Secure Attendance System',
  description: 'Student check-in interface with liveness detection',
  manifest: '/manifest.webmanifest',
  applicationName: 'SAIV Student',
  appleWebApp: { capable: true, title: 'SAIV Student', statusBarStyle: 'default' },
  icons: { icon: '/icon.svg', apple: '/icon.svg' },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#123f73',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
