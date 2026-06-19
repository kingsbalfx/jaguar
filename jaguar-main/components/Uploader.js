import { useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
import { MENTORSHIP_GROUPS, getMentorshipGroup } from "../lib/mentorship-groups";
import FeedbackMessage from "./FeedbackMessage";
import { brandVideoFile } from "../lib/client-video-branding";
import { setUploadActivity } from "../lib/activity-guard";
import { formatUploadSize, storageLimitMessage, uploadToSignedUrlWithProgress } from "../lib/signed-upload-progress";

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
  const [muteVideoAudio, setMuteVideoAudio] = useState(false);
  const group = getMentorshipGroup(segment);
  const effectiveBucket = allowSegmentSelect ? SEGMENT_BUCKETS[segment] || bucket : bucket;

  async function uploadFile(event) {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile || !client) return;
    setStatus({ type: "info", message: "Preparing secure upload..." });
    setLastUploaded(null);
    setUploadActivity(true);
    try {
      const maxSizeMb = Number(process.env.NEXT_PUBLIC_MAX_ADMIN_UPLOAD_MB || 2048);
      if (selectedFile.size > maxSizeMb * 1024 * 1024) {
        throw new Error(`File is ${formatUploadSize(selectedFile.size)}, above the ${maxSizeMb} MB upload limit.`);
      }
      const watermarkLimitMb = Number(process.env.NEXT_PUBLIC_BROWSER_WATERMARK_MAX_MB || 350);
      const file = selectedFile.type?.startsWith("video/") && selectedFile.size <= watermarkLimitMb * 1024 * 1024
        ? await brandVideoFile(
            selectedFile,
            (progress) => setStatus({ type: "info", message: `${muteVideoAudio ? "Removing audio and applying" : "Applying permanent"} KINGSBALFX watermark: ${progress}%` }),
            { muteAudio: muteVideoAudio },
          )
        : selectedFile;
      if (selectedFile.type?.startsWith("video/") && selectedFile.size > watermarkLimitMb * 1024 * 1024) {
        setStatus({ type: "info", message: `Large video detected (${formatUploadSize(selectedFile.size)}). Uploading without browser re-encoding to preserve the full file.${muteVideoAudio ? " Export this large video muted before upload to remove audio." : ""}` });
      }
      const response = await fetch("/api/admin/storage/signed-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bucket: effectiveBucket, segment: allowSegmentSelect ? segment : "all", fileName: sanitizeFileName(file.name) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to prepare upload.");
      await uploadToSignedUrlWithProgress({
        signedUrl: data.signedUrl,
        file,
        cacheControl: "3600",
        onProgress: (progress, loaded, total) => setStatus({
          type: "info",
          message: `Uploading ${formatUploadSize(total)} file: ${progress}% (${formatUploadSize(loaded)} uploaded).`,
        }),
      });
      setLastUploaded(data);
      setStatus({ type: "success", message: "Upload completed and ready to publish." });
    } catch (error) {
      setStatus({ type: "error", message: storageLimitMessage(error.message) || "Upload failed." });
    } finally {
      setUploadActivity(false);
      event.target.value = "";
    }
  }

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
        <label className="mx-auto mt-3 flex max-w-md items-start gap-2 rounded-lg border border-white/10 bg-black/20 p-3 text-left text-xs text-gray-200">
          <input type="checkbox" checked={muteVideoAudio} onChange={(event) => setMuteVideoAudio(event.target.checked)} className="mt-0.5" />
          <span>
            <span className="block font-semibold text-white">Mute video audio before upload</span>
            <span className="text-gray-400">Works during browser watermark processing for smaller videos.</span>
          </span>
        </label>
        <input type="file" onChange={uploadFile} className="mt-4 block w-full text-sm text-gray-200" />
      </div>
      <FeedbackMessage message={status.message} type={status.type || "info"} />
      {(lastUploaded?.playbackUrl || lastUploaded?.publicUrl) && (
        <a href={lastUploaded.playbackUrl || lastUploaded.publicUrl} target="_blank" rel="noreferrer" className="mx-4 mb-4 block rounded-xl border border-emerald-300/20 bg-emerald-500/10 p-3 text-xs text-emerald-200">
          Open latest upload
        </a>
      )}
    </div>
  );
}
