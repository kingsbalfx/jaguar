import { useState, useEffect } from "react";
import { supabase } from "../lib/supabase";

export default function Uploader({ bucket = "public", folder = "" }) {
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(null);
  const [listing, setListing] = useState([]);

  useEffect(() => {
    listFiles();
  }, []);

  async function uploadFile(e) {
    const f = e.target.files[0];
    if (!f) return;
    const filename = `${Date.now()}_${f.name}`;
    const path = folder ? `${folder}/${filename}` : filename;
    const { data, error } = await supabase.storage
      .from(bucket)
      .upload(path, f, { cacheControl: "3600", upsert: false });
    if (error) return alert("Upload error: " + error.message);
    alert("Uploaded: " + data.path);
    listFiles();
  }

  async function listFiles() {
    const { data, error } = await supabase.storage
      .from(bucket)
      .list(folder || "", { limit: 100, offset: 0 });
    if (error) {
      console.error(error);
      return;
    }
    setListing(data);
  }

  async function getPublicUrl(path) {
    const { data } = supabase.storage.from(bucket).getPublicUrl(path);
    return data.publicUrl;
  }

  return (
    <div className="card p-4">
      <h3 className="font-semibold">Upload to Supabase Storage</h3>
      <input type="file" onChange={uploadFile} className="mt-2" />
      <div className="mt-4">
        <h4 className="font-medium">Files</h4>
        <ul>
          {listing.map((f, i) => (
            <li key={i} className="py-1">
              {f.name} —{" "}
              <a
                target="_blank"
                rel="noreferrer"
                href={
                  supabase.storage
                    .from(bucket)
                    .getPublicUrl((folder ? folder + "/" : "") + f.name).data
                    .publicUrl
                }
              >
                Open
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
