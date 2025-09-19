import { useState } from "react";
import { supabase } from "../lib/supabase";

export default function AdminVideoPlayer({
  bucket = "public",
  initialPath = "",
}) {
  const [videoPath, setVideoPath] = useState(initialPath);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");

  const publicUrl = videoPath
    ? supabase.storage.from(bucket).getPublicUrl(videoPath).data.publicUrl
    : null;

  async function saveMetadata() {
    // placeholder: you can store metadata in Supabase table 'videos'
    alert("Metadata saved (placeholder). Title: " + title);
  }

  return (
    <div className="card p-4">
      <h3 className="font-semibold">Admin Video Player & Polishing</h3>
      <div className="mt-2">
        <label className="block">Video path (storage):</label>
        <input
          value={videoPath}
          onChange={(e) => setVideoPath(e.target.value)}
          className="w-full p-2 rounded bg-black/20"
        />
      </div>
      <div className="mt-2">
        <video
          controls
          style={{ maxWidth: "100%" }}
          src={publicUrl || ""}
        ></video>
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
      </div>
    </div>
  );
}
