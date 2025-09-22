// pages/dashboard/vip.js
import React, { useState, useEffect, useRef } from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import dynamic from "next/dynamic";
import { supabase } from "../../lib/supabaseClient";
import PriceButton from "../../components/PriceButton";

const PRICE_VIP_NGN = 150000;
const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });

export default function VipDashboard() {
  const priceFormatter = new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  });

  const [showTwilio, setShowTwilio] = useState(true);
  const [files, setFiles] = useState([]); // list of file metadata
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  const BUCKET = "vip-uploads"; // make sure this bucket exists in Supabase

  useEffect(() => {
    fetchFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchFiles() {
    try {
      const { data, error } = await supabase.storage.from(BUCKET).list("", {
        limit: 100,
        offset: 0,
        sortBy: { column: "name", order: "desc" },
      });
      if (error) {
        console.error("Storage list error:", error);
        return;
      }
      const enhanced = await Promise.all(
        (data || []).map(async (file) => {
          // getPublicUrl returns { publicUrl } inside data
          const { data: publicData } = supabase.storage.from(BUCKET).getPublicUrl(file.name);
          const publicUrl = publicData?.publicUrl || null;
          return {
            ...file,
            publicUrl,
          };
        })
      );
      setFiles(enhanced);
    } catch (err) {
      console.error("fetchFiles error:", err);
    }
  }

  function onFileChange(e) {
    setSelectedFile(e.target.files?.[0] ?? null);
    setPreviewUrl(null);
    setUploadError("");
    if (e.target.files?.[0]) {
      const f = e.target.files[0];
      const url = URL.createObjectURL(f);
      setPreviewUrl(url);
    }
  }

  async function uploadSelectedFile() {
    if (!selectedFile) {
      setUploadError("Pick a file to upload.");
      return;
    }
    setUploading(true);
    setUploadError("");
    try {
      const maxMB = 250;
      if (selectedFile.size > maxMB * 1024 * 1024) {
        throw new Error(`File too large — max ${maxMB}MB.`);
      }
      const filePath = `${Date.now()}_${selectedFile.name}`;
      const { data, error } = await supabase.storage
        .from(BUCKET)
        .upload(filePath, selectedFile, { upsert: false });
      if (error) throw error;

      // Refresh file list and clear selection
      await fetchFiles();
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setPreviewUrl(null);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadError(err?.message || String(err));
    } finally {
      setUploading(false);
    }
  }

  async function deleteFile(name) {
    if (!confirm(`Delete ${name}? This cannot be undone.`)) return;
    try {
      const { error } = await supabase.storage.from(BUCKET).remove([name]);
      if (error) throw error;
      await fetchFiles();
    } catch (err) {
      console.error("Delete error:", err);
      alert("Unable to delete file: " + (err?.message || err));
    }
  }

  function renderPreview(file) {
    if (!file?.publicUrl) return null;
    const url = file.publicUrl;
    const ext = (file.name || "").split(".").pop()?.toLowerCase();
    if (["mp4", "webm", "ogg", "mov"].includes(ext)) {
      return <ReactPlayer url={url} controls width="100%" />;
    }
    if (["mp3", "wav", "m4a", "ogg"].includes(ext)) {
      return <audio controls src={url} className="w-full" />;
    }
    if (["pdf"].includes(ext)) {
      return (
        <iframe
          title={file.name}
          src={url}
          className="w-full min-h-[400px]"
          style={{ border: "none" }}
        />
      );
    }
    if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext)) {
      return <img src={url} alt={file.name} className="max-w-full" />;
    }
    return (
      <a href={url} target="_blank" rel="noreferrer" className="underline">
        Open {file.name}
      </a>
    );
  }

  return (
    <>
      <Header />

      <main className="container mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">VIP Dashboard</h2>

          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">
              {priceFormatter.format(PRICE_VIP_NGN)}
            </div>

            <div className="mt-2 flex items-center gap-3">
              {/* Purchase link */}
              <a
                href={`/checkout?plan=vip`}
                className="inline-block px-4 py-2 bg-green-600 rounded text-white"
              >
                Purchase Access
              </a>

              {/* PriceButton rendered as sibling (not nested) */}
              <div>
                <PriceButton initialPrice={PRICE_VIP_NGN} plan="vip" />
              </div>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {/* --- left: live/twilio area --- */}
          <div className="p-4 bg-black/20 rounded">
            <h3 className="font-semibold mb-2">VIP Live Video</h3>
            <div className="bg-black/40 p-2 rounded">
              {showTwilio ? (
                <div>
                  <small className="text-gray-400">Twilio live stream below</small>
                  <div className="mt-2">
                    <div className="text-gray-300">Twilio stream component goes here.</div>
                  </div>
                </div>
              ) : (
                <div className="text-gray-300">Private live stream area</div>
              )}
            </div>
          </div>

          {/* --- right: upload, list --- */}
          <div className="p-4 bg-black/20 rounded">
            <h3 className="font-semibold mb-2">Upload Lessons (Video / Audio / Docs)</h3>
            <div className="mb-3">
              <input
                ref={fileInputRef}
                type="file"
                onChange={onFileChange}
                accept="video/*,audio/*,application/pdf,image/*,text/*"
              />
            </div>

            {previewUrl && (
              <div className="mb-3">
                <div className="font-medium mb-1">Local preview</div>
                {selectedFile && selectedFile.type.startsWith("video") ? (
                  <ReactPlayer url={previewUrl} controls width="100%" />
                ) : selectedFile && selectedFile.type.startsWith("audio") ? (
                  <audio src={previewUrl} controls className="w-full" />
                ) : selectedFile && selectedFile.type.startsWith("image") ? (
                  <img src={previewUrl} alt="preview" className="max-w-full" />
                ) : (
                  <div className="text-sm text-gray-300">{selectedFile?.name}</div>
                )}
              </div>
            )}

            <div className="flex gap-2 items-center">
              <button
                onClick={uploadSelectedFile}
                disabled={uploading}
                className="px-4 py-2 bg-green-600 rounded disabled:opacity-50"
              >
                {uploading ? "Uploading..." : "Upload"}
              </button>
              <button
                onClick={() => {
                  setSelectedFile(null);
                  setPreviewUrl(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                className="px-3 py-2 bg-gray-700 rounded"
              >
                Clear
              </button>
            </div>

            {uploadError && <div className="text-red-400 mt-2">{uploadError}</div>}

            <hr className="my-4" />

            <div>
              <h4 className="font-semibold mb-2">Uploaded files</h4>
              {files.length === 0 ? (
                <div className="text-gray-400">No files yet.</div>
              ) : (
                <ul className="space-y-3">
                  {files.map((f) => (
                    <li key={f.name} className="p-2 bg-black/10 rounded">
                      <div className="flex justify-between items-start gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium">{f.name}</div>
                          <div className="text-sm text-gray-400">
                            {f.updated_at ? new Date(f.updated_at).toLocaleString() : ""}
                          </div>

                          <div className="mt-2">{renderPreview(f)}</div>
                        </div>

                        <div className="flex flex-col items-end gap-2 ml-4">
                          <a
                            href={f.publicUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm underline"
                          >
                            Open
                          </a>
                          <button
                            onClick={() => deleteFile(f.name)}
                            className="text-sm px-2 py-1 bg-red-600 rounded"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </>
  );
}
