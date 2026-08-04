import '../styles/globals.css'
import '../styles/filters.css'
import '../styles/table.css'
import '../styles/responsive.css'
import '../styles/pagination.css'
import { Metadata, Viewport } from 'next'
import Script from 'next/script'

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_ID || 'G-5C295QK2Y0'

export const metadata: Metadata = {
  title: 'Craft Beer Alert Japan',
  description: 'Discover premium craft beers collected from the best Japanese shops.',
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'Beer Alert',
  },
}

export const viewport: Viewport = {
  themeColor: '#ffffff',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ja">
      <head>
        <Script
          src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${GA_MEASUREMENT_ID}');
          `}
        </Script>
      </head>
      <body>
        {children}
      </body>
    </html>
  )
}
