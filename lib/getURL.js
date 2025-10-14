// lib/getURL.js
export function getURL() {
  let url =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_VERCEL_URL ||
    "http://localhost:3000";
  url = url.startsWith("http") ? url : `https://${url}`;
  if (!url.endsWith("/")) url += "/";
  return url;
}