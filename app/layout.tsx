import '../public/style.css'
import '../public/pagination.css'
import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Craft Beer Alert Japan',
  description: 'Discover premium craft beers collected from the best Japanese shops.',
  manifest: '/manifest.json',
  themeColor: '#ffffff',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Beer Alert',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <body>
        {children}
      </body>
    </html>
  )
}
