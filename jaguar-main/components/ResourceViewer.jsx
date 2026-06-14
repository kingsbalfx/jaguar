import { useEffect, useRef, useState } from "react";

const ACTION_LABELS = {
  video: "Play video",
  audio: "Play audio",
  pdf: "View PDF",
  text: "Read lesson",
  link: "Open resource",
};

export default function ResourceViewer({ item, compact = false }) {
  const [open, setOpen] = useState(false);
  const [playbackError, setPlaybackError] = useState("");
  const mediaRef = useRef(null);
  const source = item.playback_url || item.public_url || item.media_url || "";
  const canOpen = item.media_type === "text" ? Boolean(item.body) : Boolean(source);

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
              {item.media_type === "video" && <video ref={mediaRef} src={source} controls playsInline preload="auto" onError={() => setPlaybackError("This video could not be played. The uploaded format may be unsupported or the storage file is missing.")} className="mx-auto aspect-video max-h-[72vh] w-full rounded-2xl bg-black" />}
              {item.media_type === "audio" && <audio ref={mediaRef} src={source} controls preload="auto" onError={() => setPlaybackError("This audio file could not be played.")} className="mt-8 w-full" />}
              {item.media_type === "pdf" && <iframe src={source} title={item.title} className="h-[72vh] w-full rounded-2xl bg-white" />}
              {item.media_type === "text" && <div className="whitespace-pre-wrap rounded-2xl bg-white/5 p-5 text-sm leading-7 text-gray-100">{item.body}</div>}
              {playbackError && <div className="mt-4 rounded-xl border border-red-300/20 bg-red-500/10 p-3 text-sm text-red-200">{playbackError}</div>}
              {source && item.media_type !== "text" && <a href={source} target="_blank" rel="noreferrer" className="mt-4 inline-flex rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-semibold text-white">Open in new tab</a>}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
