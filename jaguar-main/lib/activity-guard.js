export function setUploadActivity(active) {
  if (typeof window === "undefined") return;
  const current = Number(window.__kingsbalActiveUploads || 0);
  window.__kingsbalActiveUploads = active ? current + 1 : Math.max(0, current - 1);
  window.dispatchEvent(new CustomEvent("kingsbal:protected-activity", { detail: { type: "upload", active } }));
}
