// lib/getURL.js
export function getURL() {
  let url =
    process.env.NEXT_PUBLIC_SITE_URL ||
    process.env.NEXT_PUBLIC_DOMAIN ||
    process.env.NEXT_PUBLIC_VERCEL_URL ||
    "kingsbalfx.name.ng";
  url = url.startsWith("http") ? url : `https://${url}`;
  if (!url.endsWith("/")) url += "/";
  return url;
}
