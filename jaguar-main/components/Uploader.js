import { useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
import { MENTORSHIP_GROUPS, getMentorshipGroup } from "../lib/mentorship-groups";

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";
const SEGMENT_BUCKETS = {
  premium: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  vip: process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  pro: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  lifetime: process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
};

function sanitizeFileName(fileName = "") {
  return String(fileName).replace(/\s+/g, "_").replace(/[^a-zA-Z0-9._-]/g, "").slice(-140);
}

export default function Uploader({ bucket = DEFAULT_BUCKET, folder = "", allowSegmentSelect = false, defaultSegment = "all" }) {
  const client = useMemo(() => getBrowserSupabaseClient(), []);
  const [segment, setSegment] = useState(defaultSegment);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [lastUploaded, setLastUploaded] = useState(null);
  const group = getMentorshipGroup(segment);
  const effectiveBucket = allowSegmentSelect ? SEGMENT_BUCKETS[segment] || bucket : bucket;

  async function uploadFile(event) {
    const file = event.target.files?.[0];
    if (!file || !client) return;
    setStatus({ type: "info", message: "Preparing secure upload..." });
    setLastUploaded(null);
    try {
      const response = await fetch("/api/admin/storage/signed-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bucket: effectiveBucket, segment: allowSegmentSelect ? segment : "all", fileName: sanitizeFileName(file.name) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to prepare upload.");
      const { error } = await client.storage.from(effectiveBucket).uploadToSignedUrl(data.path, data.token, file, { cacheControl: "3600", contentType: file.type || undefined, upsert: false });
      if (error) throw error;
      setLastUploaded(data);
      setStatus({ type: "success", message: "Upload completed and ready to publish." });
    } catch (error) {
      setStatus({ type: "error", message: error.message || "Upload failed." });
    } finally {
      event.target.value = "";
    }
  }

  const statusColor = status.type === "error" ? "text-red-300" : status.type === "success" ? "text-emerald-200" : "text-gray-300";

  return (
    <div className="card overflow-hidden p-0">
      <div className={`bg-gradient-to-r ${group.accent} p-4`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-indigo-100">Quick File Drop</div>
            <h3 className="mt-1 font-semibold text-white">{group.label}</h3>
            <div className="mt-1 text-xs text-gray-300">Storage: {effectiveBucket}/{folder || "content"}</div>
          </div>
          {allowSegmentSelect && (
            <select value={segment} onChange={(event) => setSegment(event.target.value)} className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white">
              {MENTORSHIP_GROUPS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          )}
        </div>
      </div>
      <div className="m-4 rounded-xl border border-dashed border-indigo-300/25 bg-indigo-500/5 p-5 text-center">
        <div className="text-sm font-medium text-white">Choose a resource to upload</div>
        <div className="mt-1 text-xs text-gray-400">Video, audio, image, PDF, or supporting document</div>
        <input type="file" onChange={uploadFile} className="mt-4 block w-full text-sm text-gray-200" />
      </div>
      {status.message && <div className={`mx-4 mb-4 text-sm ${statusColor}`}>{status.message}</div>}
      {(lastUploaded?.playbackUrl || lastUploaded?.publicUrl) && (
        <a href={lastUploaded.playbackUrl || lastUploaded.publicUrl} target="_blank" rel="noreferrer" className="mx-4 mb-4 block rounded-xl border border-emerald-300/20 bg-emerald-500/10 p-3 text-xs text-emerald-200">
          Open latest upload
        </a>
      )}
    </div>
  );
}
