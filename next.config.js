/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'untappd.akamaized.net',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
        port: '',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: '*.beervolta.com',
      },
      {
        protocol: 'https',
        hostname: '*.arome.tokyo',
      },
      {
        protocol: 'https',
        hostname: 'ichigo-ichie.beer',
      },
      {
        protocol: 'https',
        hostname: 'placehold.co',
      }
    ],
  },
}

module.exports = nextConfig
