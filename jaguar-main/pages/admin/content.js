import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getBrowserSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";
import ResourceViewer from "../../components/ResourceViewer";
import { MENTORSHIP_GROUPS, getMentorshipGroup, getMentorshipGroupLabel } from "../../lib/mentorship-groups";
import { brandVideoFile } from "../../lib/client-video-branding";

const Uploader = dynamic(() => import("../../components/Uploader"), { ssr: false });
const AdminVideoPlayer = dynamic(() => import("../../components/AdminVideoPlayer"), { ssr: false });

const MEDIA_TYPES = [
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "pdf", label: "PDF" },
  { value: "document", label: "Document (Word, Excel, PowerPoint, text)" },
  { value: "text", label: "Text" },
  { value: "link", label: "External Link" },
];
const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";
const SEGMENT_BUCKETS = {
  premium: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  vip: process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  pro: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  lifetime: process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
};

function resolveBucket(seg) {
  if (seg && SEGMENT_BUCKETS[seg]) return SEGMENT_BUCKETS[seg];
  return DEFAULT_BUCKET;
}

export default function Content() {
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [segment, setSegment] = useState("all");
  const [mediaType, setMediaType] = useState("video");
  const [mediaUrl, setMediaUrl] = useState("");
  const [body, setBody] = useState("");
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingItem, setEditingItem] = useState(null);
  const [status, setStatus] = useState("");
  const [localPreviewUrl, setLocalPreviewUrl] = useState("");

  useEffect(() => {
    fetchItems();
  }, []);

  useEffect(() => {
    if (!file || !["video", "audio"].includes(mediaType)) {
      setLocalPreviewUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setLocalPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file, mediaType]);

  async function fetchItems() {
    const res = await fetch("/api/admin/content-items");
    const json = await res.json();
    if (res.ok) setItems(json.items || []);
  }

  async function uploadFileToStorage(fileToUpload) {
    const client = getBrowserSupabaseClient();
    if (!client) throw new Error("Supabase client not available");
    let uploadFile = fileToUpload;
    const maxSize = mediaType === "video" ? 120 * 1024 * 1024 : 30 * 1024 * 1024;
    if (fileToUpload.size > maxSize) {
      throw new Error(mediaType === "video" ? "Video must be 120 MB or less. Export as MP4 H.264 at 720p before uploading." : "File must be 30 MB or less.");
    }
    if (mediaType === "video") {
      setStatus("Applying permanent KINGSBALFX logo watermark to the video...");
      uploadFile = await brandVideoFile(fileToUpload, (progress) => setStatus(`Applying permanent KINGSBALFX watermark: ${progress}%`));
    }

    const bucket = resolveBucket(segment);
    const signedRes = await fetch("/api/admin/storage/signed-upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bucket, segment, fileName: uploadFile.name }),
    });
    const signedJson = await signedRes.json();
    if (!signedRes.ok) {
      throw new Error(signedJson?.error || "Unable to prepare secure upload");
    }

    const { path, token, publicUrl } = signedJson;
    const { error: uploadError } = await client.storage.from(bucket).uploadToSignedUrl(path, token, uploadFile, {
      cacheControl: "3600",
      contentType: uploadFile.type || undefined,
      upsert: false,
    });

    if (uploadError) {
      throw uploadError;
    }

    return { storagePath: path, publicUrl };
  }

  async function saveItem(e) {
    e.preventDefault();
    setStatus("");
    setSaving(true);
    try {
      let storagePath = null;
      let publicUrl = null;

      if (["video", "audio", "pdf", "document"].includes(mediaType)) {
        if (file) {
          const uploadResult = await uploadFileToStorage(file);
          storagePath = uploadResult.storagePath;
          publicUrl = uploadResult.publicUrl;
        } else if (!editingId) {
          throw new Error("Please select a file to upload.");
        }
      }

      if (mediaType === "link" && !mediaUrl) {
        throw new Error("Please provide a URL.");
      }

      if (mediaType === "text" && !body) {
        throw new Error("Please provide the text content.");
      }

      const payload = {
        title,
        description,
        segment,
        mediaType,
        mediaUrl: mediaType === "link" ? mediaUrl : null,
        storagePath,
        publicUrl,
        body: mediaType === "text" ? body : null,
        isPublished: true,
      };

      const res = await fetch(
        editingId ? `/api/admin/content-items/${editingId}` : "/api/admin/content-items",
        {
          method: editingId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Failed to save content");

      setStatus(editingId ? "Content updated." : "Content saved.");
      setTitle("");
      setDescription("");
      setSegment("all");
      setMediaType("video");
      setMediaUrl("");
      setBody("");
      setFile(null);
      setEditingId(null);
      setEditingItem(null);
      await fetchItems();
    } catch (err) {
      setStatus(err.message || "Failed to save content");
    } finally {
      setSaving(false);
    }
  }

  async function deleteItem(id) {
    if (!confirm("Delete this content item?")) return;
    const res = await fetch(`/api/admin/content-items/${id}`, { method: "DELETE" });
    const json = await res.json();
    if (!res.ok) {
      setStatus(json?.error || "Failed to delete content.");
      return;
    }
    setStatus("Content deleted.");
    fetchItems();
  }

  function startEdit(item) {
    setEditingId(item.id);
    setEditingItem(item);
    setTitle(item.title || "");
    setDescription(item.description || "");
    setSegment(item.segment || "all");
    setMediaType(item.media_type || "video");
    setMediaUrl(item.media_url || "");
    setBody(item.body || "");
    setFile(null);
    window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  return (
    <div className="min-h-[calc(100vh-160px)] p-4 sm:p-6">
      <div className="overflow-hidden rounded-3xl border border-indigo-300/15 bg-gradient-to-br from-indigo-600/20 via-slate-950/80 to-purple-600/15 p-5 shadow-2xl sm:p-7">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-indigo-200">Mentorship Publishing Studio</div>
            <h2 className="mt-2 text-3xl font-bold">Create a beautiful learning experience</h2>
            <p className="mt-2 max-w-2xl text-sm text-gray-300">Publish videos, audio lessons, workbooks, mentor notes, and external resources to the right learning audience.</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-xl bg-white/5 px-3 py-3"><div className="text-xl font-bold text-white">{items.length}</div><div className="text-gray-400">Resources</div></div>
            <div className="rounded-xl bg-white/5 px-3 py-3"><div className="text-xl font-bold text-emerald-300">{items.filter((item) => item.is_published).length}</div><div className="text-gray-400">Published</div></div>
            <div className="rounded-xl bg-white/5 px-3 py-3"><div className="text-xl font-bold text-purple-300">{new Set(items.map((item) => item.segment)).size}</div><div className="text-gray-400">Audiences</div></div>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="card overflow-hidden p-0">
          <div className={`bg-gradient-to-r ${getMentorshipGroup(segment).accent} p-5`}>
            <div className="text-xs uppercase tracking-widest text-indigo-100">Publishing to {getMentorshipGroupLabel(segment)}</div>
            <h3 className="mt-1 text-xl font-semibold">{editingId ? "Polish resource" : "Create new resource"}</h3>
          </div>
          <div className="p-4 sm:p-5">
          <form onSubmit={saveItem} className="space-y-3">
            <input
              className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
              placeholder="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <textarea
              className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
              placeholder="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Mentorship audience</label>
                <select
                  className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
                  value={segment}
                  onChange={(e) => setSegment(e.target.value)}
                >
                  {MENTORSHIP_GROUPS.map((group) => (
                    <option key={group.value} value={group.value}>
                      {group.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Media Type</label>
                <select
                  className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
                  value={mediaType}
                  onChange={(e) => setMediaType(e.target.value)}
                >
                  {MEDIA_TYPES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {["video", "audio", "pdf", "document"].includes(mediaType) && (
              <div className="rounded-xl border border-dashed border-indigo-300/20 bg-indigo-500/5 p-4">
                <input type="file" accept={mediaType === "video" ? "video/mp4,video/webm" : mediaType === "audio" ? "audio/mpeg,audio/mp4,audio/webm" : mediaType === "pdf" ? "application/pdf" : ".doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.rtf"} onChange={(e) => setFile(e.target.files?.[0] || null)} />
                <p className="mt-2 text-xs text-gray-400">{editingId ? "Choose a new file to replace the existing lesson, or leave it empty to keep the current file." : mediaType === "video" ? "Upload MP4 H.264 or WebM under 120 MB. Permanent KINGSBALFX branding is applied before upload and may take about the video's playback duration." : "Keep resources under 30 MB for quick downloads."}</p>
                {mediaType === "video" && (localPreviewUrl || editingItem?.playback_url) && (
                  <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-black shadow-xl">
                    <video key={localPreviewUrl || editingItem?.playback_url} src={localPreviewUrl || editingItem?.playback_url} controls preload="metadata" playsInline className="aspect-video w-full bg-black" />
                    <div className="flex items-center justify-between gap-3 px-3 py-2 text-xs text-gray-300">
                      <span>{localPreviewUrl ? "Replacement video preview" : "Current published video"}</span>
                      {localPreviewUrl && <button type="button" onClick={() => setFile(null)} className="rounded-lg bg-white/10 px-3 py-1.5 text-white">Keep current video</button>}
                    </div>
                  </div>
                )}
              </div>
            )}

            {mediaType === "link" && (
              <input
                className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
                placeholder="https://..."
                value={mediaUrl}
                onChange={(e) => setMediaUrl(e.target.value)}
              />
            )}

            {mediaType === "text" && (
              <textarea
                className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
                placeholder="Text content..."
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={6}
              />
            )}

            <div className="flex gap-3">
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 rounded bg-indigo-600 text-white disabled:opacity-60"
              >
                {saving ? "Saving..." : editingId ? "Update Content" : "Save Content"}
              </button>
              {editingId && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingId(null);
                    setTitle("");
                    setDescription("");
                    setSegment("all");
                    setMediaType("video");
                    setMediaUrl("");
                    setBody("");
                    setFile(null);
                    setEditingItem(null);
                  }}
                  className="px-4 py-2 rounded bg-gray-700 text-white"
                >
                  Cancel
                </button>
              )}
            </div>
            <FeedbackMessage message={status} type={/saved|updated|deleted/i.test(status) ? "success" : "error"} />
          </form>
          </div>
        </div>

        <div className="card p-4">
          <h3 className="text-lg font-semibold mb-4">Published Resource Gallery</h3>
          <div className="space-y-3 max-h-[520px] overflow-auto pr-2">
            {items.map((item) => (
              <div key={item.id} className={`rounded-xl border border-white/10 bg-gradient-to-br ${getMentorshipGroup(item.segment).accent} p-3`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-white">{item.title}</div>
                    <div className="text-xs text-gray-400">
                      {getMentorshipGroupLabel(item.segment)} / {item.media_type}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => startEdit(item)} className="text-xs px-2 py-1 bg-indigo-600 rounded">
                      Edit
                    </button>
                    <button onClick={() => deleteItem(item.id)} className="text-xs px-2 py-1 bg-red-600 rounded">
                      Delete
                    </button>
                  </div>
                </div>
                {item.description && <div className="text-xs text-gray-400 mt-2">{item.description}</div>}
                <ResourceViewer item={item} compact />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8">
        <h3 className="text-lg font-semibold">Storage Tools</h3>
        <p className="text-sm text-gray-400">
          Use this for manual uploads or previews. The content manager above is preferred.
        </p>
        <div className="mt-4 grid md:grid-cols-2 gap-4">
          <Uploader bucket={DEFAULT_BUCKET} folder="videos" allowSegmentSelect />
          <div>
            <Uploader bucket={DEFAULT_BUCKET} folder="images" allowSegmentSelect />
            <Uploader bucket={DEFAULT_BUCKET} folder="docs" allowSegmentSelect />
          </div>
        </div>
        <div className="mt-6">
          <AdminVideoPlayer bucket={DEFAULT_BUCKET} initialPath="videos/" />
        </div>
      </div>
    </div>
  );
}
