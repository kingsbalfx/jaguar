import { useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";
const SEGMENT_BUCKETS = {
  premium: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  vip: process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  pro: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  lifetime: process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
};
const SEGMENTS = ["all", "free", "premium", "vip", "pro", "lifetime"];

function resolveBucket(segment, fallbackBucket) {
  const key = String(segment || "").toLowerCase();
  if (SEGMENT_BUCKETS[key]) return SEGMENT_BUCKETS[key];
  return fallbackBucket || DEFAULT_BUCKET;
}

function sanitizeFileName(fileName = "") {
  return String(fileName)
    .replace(/\s+/g, "_")
    .replace(/[^a-zA-Z0-9._-]/g, "")
    .slice(-140);
}

export default function Uploader({
  bucket = DEFAULT_BUCKET,
  folder = "",
  allowSegmentSelect = false,
  defaultSegment = "all",
}) {
  const [segment, setSegment] = useState(defaultSegment);
  const [listing, setListing] = useState([]);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [lastUploaded, setLastUploaded] = useState(null);

  const effectiveBucket = useMemo(
    () => (allowSegmentSelect ? resolveBucket(segment, bucket) : bucket),
    [allowSegmentSelect, segment, bucket]
  );

  const client = useMemo(() => getBrowserSupabaseClient(), []);

  async function listFiles() {
    if (!client) return;

    const { data, error } = await client.storage
      .from(effectiveBucket)
      .list(folder || "", { limit: 100, offset: 0 });

    if (error) {
      setListing([]);
      return;
    }

    setListing(data || []);
  }

  useEffect(() => {
    void listFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveBucket, folder]);

  async function uploadFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;

    setStatus({ type: "info", message: "Preparing upload..." });
    setLastUploaded(null);

    if (!client) {
      setStatus({ type: "error", message: "Supabase client not configured in this environment." });
      return;
    }

    const safeName = sanitizeFileName(f.name || "upload");
    const filename = `${Date.now()}_${safeName}`;

    try {
      const signedRes = await fetch("/api/admin/storage/signed-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bucket: effectiveBucket,
          segment: allowSegmentSelect ? segment : "all",
          fileName: filename,
        }),
      });
      const signedJson = await signedRes.json().catch(() => ({}));

      if (!signedRes.ok) {
        setStatus({ type: "info", message: "Signed upload unavailable. Falling back to direct upload..." });
        const path = folder ? `${folder}/${filename}` : filename;
        const direct = await client.storage.from(effectiveBucket).upload(path, f, {
          cacheControl: "3600",
          upsert: false,
        });
        if (direct.error) throw direct.error;
        const publicUrl = client.storage.from(effectiveBucket).getPublicUrl(path).data.publicUrl;
        setLastUploaded({ bucket: effectiveBucket, path, publicUrl });
        setStatus({ type: "success", message: "Upload completed." });
        await listFiles();
        return;
      }

      const { path, token, publicUrl } = signedJson || {};
      if (!path || !token) throw new Error("Signed upload response missing path/token");

      setStatus({ type: "info", message: "Uploading..." });
      const { error: uploadError } = await client.storage
        .from(effectiveBucket)
        .uploadToSignedUrl(path, token, f, { cacheControl: "3600", upsert: false });
      if (uploadError) throw uploadError;

      setLastUploaded({ bucket: effectiveBucket, path, publicUrl });
      setStatus({ type: "success", message: "Upload completed." });
      await listFiles();
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Upload failed." });
    } finally {
      // Allow uploading the same file again if needed.
      e.target.value = "";
    }
  }

  const statusClass =
    status.type === "error"
      ? "text-red-300"
      : status.type === "success"
      ? "text-emerald-200"
      : "text-gray-300";

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">Storage Upload</h3>
          <div className="text-xs text-gray-400">
            Bucket: <span className="text-gray-200">{effectiveBucket}</span>
            {folder ? (
              <>
                {" "}
                · Folder: <span className="text-gray-200">{folder}</span>
              </>
            ) : null}
          </div>
        </div>

        {allowSegmentSelect && (
          <div className="min-w-[160px]">
            <label className="block text-[11px] uppercase tracking-wide text-gray-400 mb-1">
              Tier
            </label>
            <select
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white text-sm"
            >
              {SEGMENTS.map((seg) => (
                <option key={seg} value={seg}>
                  {seg.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="mt-3">
        <input type="file" onChange={uploadFile} className="block w-full text-sm text-gray-200" />
      </div>

      {status.message && <div className={`mt-3 text-sm ${statusClass}`}>{status.message}</div>}

      {lastUploaded?.publicUrl && (
        <div className="mt-3 rounded border border-white/10 bg-black/30 p-3 text-xs text-gray-200 break-words">
          <div className="text-[11px] uppercase tracking-wide text-gray-400">Last Upload</div>
          <a className="text-emerald-200 hover:underline" href={lastUploaded.publicUrl} target="_blank" rel="noreferrer">
            {lastUploaded.publicUrl}
          </a>
        </div>
      )}

      <div className="mt-4">
        <h4 className="font-medium text-white">Files</h4>
        <ul className="mt-2 space-y-1 text-sm">
          {listing.map((item) => {
            const name = item?.name;
            const url = client?.storage
              .from(effectiveBucket)
              .getPublicUrl((folder ? `${folder}/` : "") + name).data.publicUrl;
            return (
              <li key={name} className="py-1 text-gray-200">
                <span className="text-gray-300">{name}</span>{" "}
                <span className="text-gray-500">-</span>{" "}
                <a target="_blank" rel="noreferrer" href={url} className="text-emerald-200 hover:underline">
                  Open
                </a>
              </li>
            );
          })}
          {listing.length === 0 && (
            <li className="py-1 text-gray-400">No files listed (bucket may be private or empty).</li>
          )}
        </ul>
      </div>
    </div>
  );
}
