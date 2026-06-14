import { useState } from "react";
import FeedbackMessage from "./FeedbackMessage";

export default function AdminVideoPlayer({
  bucket = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public",
  initialPath = "",
}) {
  const [videoPath, setVideoPath] = useState(initialPath);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [message, setMessage] = useState("");
  const [playbackUrl, setPlaybackUrl] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadVideo() {
    if (!videoPath.trim()) return setMessage("Enter the full storage path first.");
    setLoading(true);
    setMessage("");
    try {
      const response = await fetch("/api/admin/storage/signed-view", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bucket, path: videoPath.trim() }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to load video.");
      setPlaybackUrl(data.playbackUrl);
      setMessage("Secure video preview ready.");
    } catch (error) {
      setPlaybackUrl("");
      setMessage(error.message || "Unable to load video.");
    } finally {
      setLoading(false);
    }
  }

  async function saveMetadata() {
    setMessage(`Metadata prepared for "${title || "Untitled video"}".`);
  }

  return (
    <div className="card p-4">
      <h3 className="font-semibold">Admin Video Player & Polishing</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
        <label className="block">Video path (storage):</label>
        <input
          value={videoPath}
          onChange={(e) => setVideoPath(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 p-3"
        />
        <button type="button" onClick={loadVideo} disabled={loading} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          {loading ? "Loading..." : "Preview video"}
        </button>
      </div>
      <div className="mt-4 overflow-hidden rounded-2xl border border-white/10 bg-black">
        <video
          controls
          playsInline
          preload="metadata"
          className="aspect-video w-full bg-black"
          src={playbackUrl}
        />
      </div>
      <div className="mt-2">
        <input
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full p-2 rounded bg-black/20"
        />
        <textarea
          placeholder="Description"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          className="w-full p-2 rounded bg-black/20 mt-2"
        ></textarea>
        <div className="mt-2">
          <button onClick={saveMetadata} className="card px-3 py-2">
            Save metadata
          </button>
        </div>
        <FeedbackMessage message={message} type="success" className="mt-3" />
      </div>
    </div>
  );
}
