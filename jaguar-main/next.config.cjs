// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Environment variables available in both build and runtime
  env: {
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  },

  // Images settings
  images: {
    domains: [
      'lh3.googleusercontent.com',
      'images.unsplash.com',
      'cdn.pixabay.com',
      'res.cloudinary.com'
    ],
    unoptimized: true,
  },

  // Redirects for route cleanup
  async redirects() {
    return [
      { source: '/admin', destination: '/admin/index', permanent: false },
      { source: '/vip', destination: '/dashboard/vip', permanent: false },
      { source: '/premium', destination: '/dashboard/premium', permanent: false },
      { source: '/mentorship', destination: '/admin/mentorship', permanent: false },
      { source: '/checkout/success', destination: '/checkout/success', permanent: false },
    ];
  },

  // Rewrites to handle sub-paths correctly
  async rewrites() {
    return [
      { source: '/api/:path*', destination: '/api/:path*' },
      { source: '/auth/:path*', destination: '/auth/:path*' },
      { source: '/dashboard/:path*', destination: '/dashboard/:path*' },
      { source: '/admin/:path*', destination: '/admin/:path*' },
      { source: '/mentorship/:path*', destination: '/admin/mentorship/:path*' },
      { source: '/checkout/:path*', destination: '/checkout/:path*' },
    ];
  },

  // PWA settings (if you’re using next-pwa)
  pwa: {
    dest: 'public',
    disable: process.env.ENABLE_PWA !== 'true',
    register: true,
    skipWaiting: true,
  },
};

module.exports = nextConfig;
