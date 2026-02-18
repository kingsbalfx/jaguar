// pages/dashboard/vip.js
import React, { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import { supabase } from "../../lib/supabaseClient";
import PriceButton from "../../components/PriceButton";

const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });
const PRICE_VIP_NGN = 150000;

export default function VipDashboard() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);
  const BUCKET = "vip-uploads";
  const priceFormatter = new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 });

  useEffect(() => {
    fetchFiles();
  }, []);

  async function fetchFiles() {
    try {
      const { data, error } = await supabase.storage.from(BUCKET).list("", { limit: 100, offset: 0, sortBy: { column: "name", order: "desc" } });
      if (error) {
        console.error("Storage list error:", error);
        return;
      }
      const enhanced = (data || []).map(file => {
        const { publicURL } = supabase.storage.from(BUCKET).getPublicUrl(file.name);
        // NOTE: old SDK returned { publicUrl }, the new getPublicUrl returns { data: { publicUrl } } - adjust if needed.
        // We'll attempt to derive public URL robustly:
        const pub = publicURL || (file?.publicUrl) || null;
        return { ...file, publicUrl: pub };
      });
      setFiles(enhanced);
    } catch (err) {
      console.error("fetchFiles error:", err);
    }
  }

  function onFileChange(e) {
    const f = e.target.files?.[0] ?? null;
    setSelectedFile(f);
    setUploadError("");
    setPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

  async function uploadSelectedFile() {
    if (!selectedFile) {
      setUploadError("Pick a file.");
      return;
    }
    setUploading(true);
    try {
      const maxMB = 250;
      if (selectedFile.size > maxMB * 1024 * 1024) throw new Error(`File too large. Max ${maxMB}MB`);

      const filePath = `${Date.now()}_${selectedFile.name}`;
      const { error } = await supabase.storage.from(BUCKET).upload(filePath, selectedFile, { upsert: false });
      if (error) throw error;
      await fetchFiles();
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setPreviewUrl(null);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err?.message || "Upload error");
    } finally {
      setUploading(false);
    }
  }

  async function deleteFile(name) {
    if (!confirm(`Delete ${name}?`)) return;
    try {
      const { error } = await supabase.storage.from(BUCKET).remove([name]);
      if (error) throw error;
      await fetchFiles();
    } catch (err) {
      console.error("Delete error:", err);
      alert("Delete failed");
    }
  }

  function renderPreview(file) {
    if (!file?.publicUrl) return null;
    const ext = (file.name || "").split(".").pop()?.toLowerCase();
    if (["mp4", "webm", "ogg", "mov"].includes(ext)) return <video src={file.publicUrl} controls className="max-w-full rounded" />;
    if (["jpg", "jpeg", "png", "gif"].includes(ext)) return <img src={file.publicUrl} alt={file.name} className="max-w-full rounded" />;
    return <a href={file.publicUrl} target="_blank" rel="noreferrer">{file.name}</a>;
  }

  return (
    <main className="container mx-auto px-6 py-8 text-white">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">VIP Dashboard</h2>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceFormatter.format(PRICE_VIP_NGN)}</div>
            <div className="mt-2 flex gap-3">
              <a href={`/checkout?plan=vip`} className="px-3 py-2 bg-indigo-600 rounded">Checkout</a>
              <PriceButton initialPrice={PRICE_VIP_NGN} plan="vip" />
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Live Video</h3>
            <div className="bg-black/40 p-2 rounded">
              <ReactPlayer url="https://www.youtube.com/watch?v=dQw4w9WgXcQ" controls width="100%" />
            </div>
          </div>

          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Upload Lessons</h3>
            <div className="mb-3">
              <input ref={fileInputRef} type="file" onChange={onFileChange} />
            </div>

            {previewUrl && <div className="mb-3"><div className="text-sm mb-1">Local preview</div><img src={previewUrl} alt="preview" className="max-w-full rounded" /></div>}

            <div className="flex gap-2">
              <button onClick={uploadSelectedFile} disabled={uploading} className="px-4 py-2 bg-green-600 rounded">
                {uploading ? "Uploading…" : "Upload"}
              </button>
              <button onClick={() => { setSelectedFile(null); setPreviewUrl(null); if (fileInputRef.current) fileInputRef.current.value = ""; }} className="px-3 py-2 bg-gray-700 rounded">Clear</button>
            </div>
            {uploadError && <div className="text-red-400 mt-2">{uploadError}</div>}

            <hr className="my-4" />
            <h4 className="font-semibold mb-2">Uploaded files</h4>
            {files.length === 0 ? <div className="text-gray-400">No files yet.</div> : files.map(f => (
              <div key={f.name} className="flex justify-between items-center mb-2">
                <div>{f.name}</div>
                <div className="flex gap-2">
                  <button onClick={() => deleteFile(f.name)} className="text-red-400">Delete</button>
                  <button onClick={() => window.open(f.publicUrl, "_blank")} className="text-blue-400">View</button>
                </div>
              </div>
            ))}
          </div>
        </div>
    </main>
  );
}
