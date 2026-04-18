/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'untappd.akamaized.net',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '*.untappd.com',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '*.beervolta.com',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '*.arome.tokyo',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'www.arome.jp',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'beer-chouseiya.shop',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '151l.shop',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'ichigo-ichie.beer',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'placehold.co',
        pathname: '/**',
      }
    ],
  },
}

module.exports = nextConfig
