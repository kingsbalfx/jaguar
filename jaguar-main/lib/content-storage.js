export const DEFAULT_CONTENT_BUCKET = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";

export const CONTENT_SEGMENT_BUCKETS = {
  premium: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  vip: process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  pro: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  lifetime: process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
};

export function getContentBucket(segment, storagePath = "") {
  const pathSegment = String(storagePath).match(/^content\/([^/]+)\//)?.[1]?.toLowerCase();
  return CONTENT_SEGMENT_BUCKETS[pathSegment] || CONTENT_SEGMENT_BUCKETS[String(segment || "").toLowerCase()] || DEFAULT_CONTENT_BUCKET;
}

export async function addContentMediaUrls(supabaseAdmin, item, expiresIn = 60 * 60 * 6) {
  if (!item?.storage_path) return item;
  const bucket = getContentBucket(item.segment, item.storage_path);
  const [{ data: playback, error }, { data: download }] = await Promise.all([
    supabaseAdmin.storage.from(bucket).createSignedUrl(item.storage_path, expiresIn),
    supabaseAdmin.storage.from(bucket).createSignedUrl(item.storage_path, expiresIn, { download: item.title || true }),
  ]);

  return {
    ...item,
    storage_bucket: bucket,
    playback_url: error ? item.public_url || null : playback?.signedUrl || item.public_url || null,
    download_url: download?.signedUrl || playback?.signedUrl || item.public_url || null,
  };
}
