// components/UploadPanel.js
import { useState } from "react";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

const DEFAULT_BUCKET = process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";

export default function UploadPanel() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  async function upload() {
    if (!file) return setStatus("Select a file first.");
    setStatus("Uploading...");
    const fileExt = file.name.split(".").pop();
    const filePath = `${Date.now()}_${file.name}`;

    const { data, error } = await supabase.storage
      .from(DEFAULT_BUCKET)             // make sure this bucket exists in Supabase Storage
      .upload(filePath, file, {
        cacheControl: "3600",
        upsert: false,
      });

    if (error) {
      setStatus("Upload error: " + error.message);
    } else {
      setStatus("Uploaded: " + data.path);
    }
  }

  return (
    <div>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button onClick={upload}>Upload</button>
      <div>{status}</div>
    </div>
  );
}
