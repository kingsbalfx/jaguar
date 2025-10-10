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
    style: "currency", currency: "NGN", maximumFractionDigits: 0
  });
  const [showTwilio, setShowTwilio] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  const BUCKET = "vip-uploads"; // Supabase storage bucket

  useEffect(() => {
    fetchFiles();
  }, []);

  async function fetchFiles() {
    try {
      const { data, error } = await supabase.storage.from(BUCKET).list("", {
        limit: 100, offset: 0, sortBy: { column: "name", order: "desc" }
      });
      if (error) {
        console.error("Storage list error:", error);
        return;
      }
      const enhanced = await Promise.all(
        (data || []).map(async (file) => {
          const { data: publicData } = supabase.storage.from(BUCKET).getPublicUrl(file.name);
          const publicUrl = publicData?.publicUrl || null;
          return { ...file, publicUrl };
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
      setPreviewUrl(URL.createObjectURL(f));
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
      const { error } = await supabase.storage.from(BUCKET).upload(filePath, selectedFile);
      if (error) throw error;
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
    const ext = (file.name || "").split(".").pop()?.toLowerCase();
    if (["mp4", "webm", "ogg", "mov"].includes(ext)) {
      return <video src={file.publicUrl} controls className="max-w-full h-auto rounded" />;
    }
    if (["jpg", "jpeg", "png", "gif"].includes(ext)) {
      return <img src={file.publicUrl} alt={file.name} className="max-w-full h-auto rounded" />;
    }
    return <a href={file.publicUrl} target="_blank" rel="noopener noreferrer">{file.name}</a>;
  }

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8 text-white">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">VIP Dashboard</h2>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access Price</div>
            <div className="text-lg font-semibold text-yellow-300">
              {priceFormatter.format(PRICE_VIP_NGN)}
            </div>
            <div className="mt-2">
              <a
                href={`/checkout?plan=vip`}
                className="inline-block px-3 py-2 bg-indigo-600 rounded text-white"
              >
                Purchase Access
              </a>
              <PriceButton initialPrice={PRICE_VIP_NGN} plan="vip" className="inline-block ml-3" />
            </div>
          </div>
        </div>

        <div className="flex gap-4 mb-4">
          <button
            className="px-4 py-2 bg-indigo-600 rounded"
            onClick={() => setShowTwilio(false)}
          >
            Watch YouTube
          </button>
          <button
            className="px-4 py-2 bg-green-600 rounded"
            onClick={() => setShowTwilio(true)}
          >
            Join Twilio Live
          </button>
        </div>

        {!showTwilio ? (
          <div className="grid md:grid-cols-2 gap-6">
            <div className="p-4 bg-gray-800 rounded">
              <h3 className="font-semibold mb-2">Live Video (YouTube)</h3>
              <div className="bg-black/40 p-2 rounded">
                <ReactPlayer
                  url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                  controls
                  width="100%"
                />
              </div>
            </div>

            <div className="p-4 bg-gray-800 rounded">
              <h3 className="font-semibold mb-2">Latest Lesson</h3>
              <p className="text-gray-300">
                Video, documents, images and audio uploads are accessible here.
              </p>
              {/* Upload form */}
              <div className="mt-4">
                <input
                  type="file"
                  onChange={onFileChange}
                  ref={fileInputRef}
                  className="mb-2"
                />
                {previewUrl && (
                  <div className="mb-2">
                    <div className="text-sm text-gray-200">Preview:</div>
                    <img src={previewUrl} alt="preview" className="max-w-full h-auto rounded" />
                  </div>
                )}
                {uploadError && (
                  <div className="text-red-500 text-sm mb-2">{uploadError}</div>
                )}
                <button
                  onClick={uploadSelectedFile}
                  disabled={uploading}
                  className="px-4 py-2 bg-blue-500 rounded disabled:opacity-60"
                >
                  {uploading ? "Uploading…" : "Upload"}
                </button>
              </div>
              {/* File list */}
              <div className="mt-4">
                {files.map((f) => (
                  <div key={f.name} className="flex items-center justify-between mb-2">
                    <div>{f.name}</div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => deleteFile(f.name)}
                        className="text-red-400 hover:text-red-600"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => window.open(f.publicUrl, "_blank")}
                        className="text-blue-400 hover:text-blue-600"
                      >
                        View
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Twilio Live (VIP)</h3>
            {/* Placeholder for Twilio live component */}
            <div className="text-gray-400">Twilio video stream would appear here.</div>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}