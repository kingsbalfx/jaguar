export async function brandVideoFile(file, onProgress = () => {}, options = {}) {
  if (!file?.type?.startsWith("video/")) return file;
  if (typeof document === "undefined" || typeof MediaRecorder === "undefined") {
    throw new Error("This browser cannot apply the permanent KINGSBALFX video watermark. Use current Chrome or Edge.");
  }

  const sourceUrl = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.src = sourceUrl;
  const muteAudio = Boolean(options.muteAudio);
  video.muted = muteAudio;
  video.playsInline = true;
  video.preload = "auto";
  await once(video, "loadedmetadata");
  const sourceDuration = Number.isFinite(video.duration) ? video.duration : 0;
  video.currentTime = 0;

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth || 1280;
  canvas.height = video.videoHeight || 720;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") {
    URL.revokeObjectURL(sourceUrl);
    throw new Error("This browser cannot apply the permanent KINGSBALFX video watermark. Use current Chrome or Edge.");
  }

  const logo = new Image();
  logo.src = "/jaguar.png";
  await Promise.race([once(logo, "load"), new Promise((resolve) => window.setTimeout(resolve, 1500))]);
  const output = canvas.captureStream(24);
  const sourceStream = video.captureStream?.() || video.mozCaptureStream?.();
  if (!muteAudio) sourceStream?.getAudioTracks().forEach((track) => output.addTrack(track));
  const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus") ? "video/webm;codecs=vp9,opus" : "video/webm";
  const recorder = new MediaRecorder(output, { mimeType, videoBitsPerSecond: 1800000 });
  const chunks = [];
  recorder.ondataavailable = (event) => {
    if (event.data?.size) chunks.push(event.data);
  };

  let frameId;
  let lastProgress = -1;
  const draw = () => {
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    drawWatermark(context, logo, canvas.width);
    const progress = video.duration ? Math.min(99, Math.round((video.currentTime / video.duration) * 100)) : 0;
    if (progress !== lastProgress) {
      lastProgress = progress;
      onProgress(progress);
    }
    frameId = window.requestAnimationFrame(draw);
  };

  const finished = new Promise((resolve, reject) => {
    recorder.onerror = () => reject(new Error("Unable to apply the permanent video watermark."));
    recorder.onstop = resolve;
  });
  recorder.start(1000);
  await video.play();
  draw();
  await once(video, "ended");
  await new Promise((resolve) => window.setTimeout(resolve, 350));
  try { recorder.requestData(); } catch {}
  recorder.stop();
  await finished;
  window.cancelAnimationFrame(frameId);
  output.getTracks().forEach((track) => track.stop());
  URL.revokeObjectURL(sourceUrl);
  onProgress(100);

  const baseName = String(file.name || "video").replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9_-]+/g, "_");
  const brandedBlob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
  if (sourceDuration > 5) {
    const brandedDuration = await readVideoDuration(brandedBlob);
    if (brandedDuration && brandedDuration + 2 < sourceDuration) {
      throw new Error("The browser produced a shortened watermarked video. Please try Chrome/Edge again or export the lesson as MP4 H.264 before uploading.");
    }
  }
  return new File([brandedBlob], `KINGSBALFX_${baseName}.webm`, { type: recorder.mimeType || "video/webm" });
}

function drawWatermark(context, logo, width) {
  const padding = Math.max(14, Math.round(width * 0.015));
  const logoSize = Math.max(44, Math.round(width * 0.055));
  const boxWidth = Math.max(210, Math.round(width * 0.22));
  const boxHeight = logoSize + padding;
  const x = width - boxWidth - padding;
  const y = padding;
  context.fillStyle = "rgba(0, 0, 0, 0.62)";
  context.fillRect(x, y, boxWidth, boxHeight);
  if (logo.complete) context.drawImage(logo, x + padding / 2, y + padding / 2, logoSize, logoSize);
  context.fillStyle = "#ffffff";
  context.font = `700 ${Math.max(18, Math.round(width * 0.022))}px sans-serif`;
  context.fillText("KINGSBALFX", x + logoSize + padding, y + boxHeight * 0.62);
}

function once(target, event) {
  return new Promise((resolve, reject) => {
    target.addEventListener(event, resolve, { once: true });
    target.addEventListener("error", () => reject(new Error("Unable to process the selected video file.")), { once: true });
  });
}

function readVideoDuration(blob) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const probe = document.createElement("video");
    const cleanup = () => URL.revokeObjectURL(url);
    probe.preload = "metadata";
    probe.onloadedmetadata = () => {
      const duration = Number.isFinite(probe.duration) ? probe.duration : 0;
      cleanup();
      resolve(duration);
    };
    probe.onerror = () => {
      cleanup();
      resolve(0);
    };
    probe.src = url;
  });
}
