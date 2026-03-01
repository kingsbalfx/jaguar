import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getBrowserSupabaseClient } from "../../lib/supabaseClient";

const Uploader = dynamic(() => import("../../components/Uploader"), { ssr: false });
const AdminVideoPlayer = dynamic(() => import("../../components/AdminVideoPlayer"), { ssr: false });

const SEGMENTS = ["all", "free", "premium", "vip", "pro", "lifetime"];
const MEDIA_TYPES = [
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "pdf", label: "PDF" },
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
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetchItems();
  }, []);

  async function fetchItems() {
    const res = await fetch("/api/admin/content-items");
    const json = await res.json();
    if (res.ok) setItems(json.items || []);
  }

  async function uploadFileToStorage(fileToUpload) {
    const client = getBrowserSupabaseClient();
    if (!client) throw new Error("Supabase client not available");

    const bucket = resolveBucket(segment);
    const filename = `${Date.now()}_${fileToUpload.name}`;
    const path = `content/${segment}/${filename}`;
    const { data, error } = await client.storage.from(bucket).upload(path, fileToUpload, {
      cacheControl: "3600",
      upsert: false,
    });
    if (error) throw error;
    const publicUrl = client.storage.from(bucket).getPublicUrl(data.path).data.publicUrl;
    return { storagePath: data.path, publicUrl };
  }

  async function saveItem(e) {
    e.preventDefault();
    setStatus("");
    setSaving(true);
    try {
      let storagePath = null;
      let publicUrl = null;

      if (["video", "audio", "pdf"].includes(mediaType)) {
        if (!file) throw new Error("Please select a file to upload.");
        const uploadResult = await uploadFileToStorage(file);
        storagePath = uploadResult.storagePath;
        publicUrl = uploadResult.publicUrl;
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
      alert(json?.error || "Failed to delete");
      return;
    }
    fetchItems();
  }

  function startEdit(item) {
    setEditingId(item.id);
    setTitle(item.title || "");
    setDescription(item.description || "");
    setSegment(item.segment || "all");
    setMediaType(item.media_type || "video");
    setMediaUrl(item.media_url || "");
    setBody(item.body || "");
    setFile(null);
  }

  return (
    <div className="p-6 min-h-[calc(100vh-160px)]">
      <h2 className="text-2xl font-bold">Content Manager</h2>
      <p className="mt-2 text-gray-300">
        Upload videos, audio, PDFs, or text content and assign them to subscriber segments.
      </p>

      <div className="mt-4 grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
        <div className="card p-4">
          <h3 className="font-semibold mb-4">Add Content</h3>
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
                <label className="block text-xs text-gray-400 mb-1">Segment</label>
                <select
                  className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
                  value={segment}
                  onChange={(e) => setSegment(e.target.value)}
                >
                  {SEGMENTS.map((seg) => (
                    <option key={seg} value={seg}>
                      {seg.toUpperCase()}
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

            {["video", "audio", "pdf"].includes(mediaType) && (
              <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
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
                  }}
                  className="px-4 py-2 rounded bg-gray-700 text-white"
                >
                  Cancel
                </button>
              )}
            </div>
            {status && <div className="text-sm text-gray-300">{status}</div>}
          </form>
        </div>

        <div className="card p-4">
          <h3 className="font-semibold mb-4">Existing Content</h3>
          <div className="space-y-3 max-h-[520px] overflow-auto pr-2">
            {items.map((item) => (
              <div key={item.id} className="border border-white/10 rounded p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-white">{item.title}</div>
                    <div className="text-xs text-gray-400">
                      {item.segment?.toUpperCase()} â€¢ {item.media_type}
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
          <Uploader bucket={DEFAULT_BUCKET} folder="videos" />
          <div>
            <Uploader bucket={DEFAULT_BUCKET} folder="images" />
            <Uploader bucket={DEFAULT_BUCKET} folder="docs" />
          </div>
        </div>
        <div className="mt-6">
          <AdminVideoPlayer bucket={DEFAULT_BUCKET} initialPath="videos/" />
        </div>
      </div>
    </div>
  );
}
