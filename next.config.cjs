// next.config.mjs

import withPWA from 'next-pwa';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  images: {
    domains: [
      'lh3.googleusercontent.com',
      'images.unsplash.com'
      // add more if needed
    ],
    unoptimized: true
  },

  // If you need other output behavior, ensure only valid keys per Next.js 15 docs
  // For example, this is valid:
  // outputFileTracing: true,
  // output: { ... } only with valid subkeys

  // next-pwa plugin usage
  pwa: {
    dest: 'public',
    disable: process.env.ENABLE_PWA !== 'true'
    // Do NOT include invalid keys here
  }
};

export default withPWA(nextConfig);
