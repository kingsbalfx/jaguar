import { useEffect, useRef, useState } from "react";

const ACTION_LABELS = {
  video: "Play video",
  audio: "Play audio",
  pdf: "View PDF",
  document: "View document",
  text: "Read lesson",
  link: "Open resource",
};

export default function ResourceViewer({ item, compact = false }) {
  const [open, setOpen] = useState(false);
  const [playbackError, setPlaybackError] = useState("");
  const mediaRef = useRef(null);
  const source = item.playback_url || item.public_url || item.media_url || "";
  const downloadSource = item.download_url || source;
  const canOpen = item.media_type === "text" ? Boolean(item.body) : Boolean(source);

  const downloadTextLesson = () => {
    const brandedText = `KINGSBALFX\n${item.title || "Mentorship Lesson"}\n\n${item.description || ""}\n\n${item.body || ""}\n\n© ${new Date().getFullYear()} KINGSBALFX. All rights reserved.`;
    const url = URL.createObjectURL(new Blob([brandedText], { type: "text/plain;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `KINGSBALFX_${String(item.title || "lesson").replace(/[^a-zA-Z0-9_-]+/g, "_")}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    if (!open || item.media_type !== "video") return;
    mediaRef.current?.play().catch(() => {});
  }, [open, item.media_type]);

  if (item.media_type === "link" && source) {
    return <a href={source} target="_blank" rel="noreferrer" className="mt-3 inline-flex rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg">Open resource</a>;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setPlaybackError("");
          setOpen(true);
        }}
        disabled={!canOpen}
        className={`${compact ? "mt-3 w-full" : "mt-4"} inline-flex items-center justify-center rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-400`}
      >
        {canOpen ? ACTION_LABELS[item.media_type] || "View content" : "Content file unavailable"}
      </button>

      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 p-3 backdrop-blur-sm sm:p-6" role="dialog" aria-modal="true" aria-label={item.title}>
          <div className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-white/15 bg-[#0b141a] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-white/10 bg-[#202c33] px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <div className="truncate text-lg font-semibold text-white">{item.title}</div>
                {item.description && <div className="mt-1 line-clamp-2 text-sm text-gray-300">{item.description}</div>}
              </div>
              <button type="button" onClick={() => setOpen(false)} className="shrink-0 rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold text-white">Close</button>
            </div>
            <div className="overflow-auto p-3 sm:p-5">
              {item.media_type === "video" && <div className="relative overflow-hidden rounded-2xl bg-black"><video ref={mediaRef} src={source} controls playsInline preload="auto" onError={() => setPlaybackError("This video could not be played. The uploaded format may be unsupported or the storage file is missing.")} className="mx-auto aspect-video max-h-[72vh] w-full bg-black" /><BrandWatermark /></div>}
              {item.media_type === "audio" && <div className="relative mt-8 rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 to-emerald-950 p-8"><BrandWatermark /><audio ref={mediaRef} src={source} controls preload="auto" onError={() => setPlaybackError("This audio file could not be played.")} className="relative z-10 w-full" /></div>}
              {item.media_type === "pdf" && <div className="relative"><iframe src={source} title={item.title} className="h-[72vh] w-full rounded-2xl bg-white" /><BrandWatermark /></div>}
              {item.media_type === "document" && <div className="rounded-2xl border border-white/10 bg-white/5 p-8 text-center"><img src="/jaguar.png" alt="" className="mx-auto h-20 w-20 object-contain opacity-70" /><div className="mt-3 text-xl font-semibold">KINGSBALFX Document</div><p className="mt-2 text-sm text-gray-300">Download this branded resource to open it in the appropriate document application.</p></div>}
              {item.media_type === "text" && <div className="whitespace-pre-wrap rounded-2xl bg-white/5 p-5 text-sm leading-7 text-gray-100">{item.body}</div>}
              {playbackError && <div className="mt-4 rounded-xl border border-red-300/20 bg-red-500/10 p-3 text-sm text-red-200">{playbackError}</div>}
              {source && item.media_type !== "text" && <a href={source} target="_blank" rel="noreferrer" className="mt-4 inline-flex rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-semibold text-white">Open in new tab</a>}
              {downloadSource && <a href={downloadSource} download className="ml-2 mt-4 inline-flex rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Download KINGSBALFX copy</a>}
              {item.media_type === "text" && <button type="button" onClick={downloadTextLesson} className="ml-2 mt-4 inline-flex rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Download KINGSBALFX copy</button>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function BrandWatermark() {
  return (
    <div className="pointer-events-none absolute right-3 top-3 z-20 flex items-center gap-2 rounded-xl border border-white/15 bg-black/55 px-2.5 py-1.5 text-white shadow-lg backdrop-blur-sm">
      <img src="/jaguar.png" alt="" className="h-7 w-7 object-contain" />
      <span className="text-xs font-bold tracking-wider">KINGSBALFX</span>
    </div>
  );
}
