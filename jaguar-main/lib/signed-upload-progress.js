export function formatUploadSize(bytes = 0) {
  const mb = Number(bytes || 0) / 1024 / 1024;
  return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
}

export function storageLimitMessage(errorMessage = "") {
  const message = String(errorMessage || "");
  if (/exceed|maximum|too large|entity too large|payload/i.test(message)) {
    return "Upload is larger than the current Supabase bucket limit. Increase the bucket file-size limit in Supabase Storage for 500MB-2GB files, then retry this same upload.";
  }
  return message;
}

export function uploadToSignedUrlWithProgress({
  signedUrl,
  file,
  cacheControl = "3600",
  upsert = false,
  onProgress = () => {},
}) {
  if (!signedUrl) return Promise.reject(new Error("Signed upload URL is missing."));
  if (!file?.size) return Promise.reject(new Error("Upload file is empty."));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("cacheControl", cacheControl);
    formData.append("", file);

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      const percent = Math.max(1, Math.min(99, Math.round((event.loaded / event.total) * 100)));
      onProgress(percent, event.loaded, event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(100, file.size, file.size);
        resolve({ ok: true });
        return;
      }
      let detail = xhr.responseText || `Upload failed with status ${xhr.status}.`;
      try {
        const parsed = JSON.parse(xhr.responseText);
        detail = parsed.error || parsed.message || detail;
      } catch {}
      reject(new Error(storageLimitMessage(detail)));
    };
    xhr.onerror = () => reject(new Error("Network error while uploading. Keep the page open and retry on a stable connection."));
    xhr.onabort = () => reject(new Error("Upload was cancelled before it finished."));
    xhr.open("PUT", signedUrl);
    xhr.setRequestHeader("x-upsert", String(Boolean(upsert)));
    const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (anonKey) {
      xhr.setRequestHeader("apikey", anonKey);
      xhr.setRequestHeader("authorization", `Bearer ${anonKey}`);
    }
    xhr.send(formData);
  });
}
