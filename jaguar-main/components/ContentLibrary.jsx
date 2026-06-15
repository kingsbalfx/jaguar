import { useEffect, useState } from "react";
import { getMentorshipGroup } from "../lib/mentorship-groups";
import ResourceViewer from "./ResourceViewer";
import FeedbackMessage from "./FeedbackMessage";

const MEDIA_LABELS = { video: "Watch lesson", audio: "Listen", pdf: "Open workbook", document: "Open document", text: "Read lesson", link: "Open resource" };

export default function ContentLibrary() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadItems();
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") loadItems();
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, []);

  async function loadItems() {
    setLoading(true);
    try {
      const res = await fetch("/api/content/items", { cache: "no-store" });
      const data = await res.json();
      if (!res.ok || !data?.items) throw new Error(data?.error || "Unable to load content.");
      setItems((current) => {
        const existingById = new Map(current.map((item) => [item.id, item]));
        return data.items.map((item) => {
          const existing = existingById.get(item.id);
          if (!existing || existing.storage_path !== item.storage_path) return item;
          return {
            ...item,
            playback_url: existing.playback_url || item.playback_url,
            download_url: existing.download_url || item.download_url,
          };
        });
      });
      setError("");
    } catch (err) {
      setError(err.message || "Unable to load content.");
    } finally {
      setLoading(false);
    }
  }

  if (error && !items.length) return (
    <>
      <div className="mt-6 rounded-2xl border border-dashed border-indigo-300/20 bg-indigo-500/5 p-8 text-center text-gray-300">
        <div className="text-lg font-semibold text-white">Learning library temporarily unavailable</div>
        <div className="mt-2 text-sm">Please retry while we reconnect to your protected resources.</div>
        <button type="button" onClick={loadItems} className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 font-semibold text-white">Try again</button>
      </div>
      <FeedbackMessage message={error} type="error" />
    </>
  );
  if (!items.length) return (
    <div className="mt-6 rounded-2xl border border-dashed border-indigo-300/20 bg-indigo-500/5 p-8 text-center text-gray-300">
      <div className="text-lg font-semibold text-white">Your learning library is ready</div>
      <div className="mt-2 text-sm">New lessons and resources published for your group will appear here.</div>
      <button type="button" onClick={loadItems} disabled={loading} className="mt-4 rounded-lg border border-indigo-300/20 bg-indigo-500/10 px-4 py-2 text-sm font-semibold text-indigo-100 disabled:opacity-60">
        {loading ? "Checking..." : "Check for new lessons"}
      </button>
    </div>
  );

  return (
    <section className="mt-8 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/55 p-4 shadow-2xl sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.22em] text-indigo-200">Mentorship Library</div>
          <h3 className="mt-1 text-2xl font-semibold">Your Learning Resources</h3>
          <p className="mt-1 text-sm text-gray-300">Lessons, recordings, workbooks, and mentor notes selected for your group.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-full border border-emerald-300/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{items.length} resources available</div>
          <button type="button" onClick={loadItems} disabled={loading} className="rounded-full border border-indigo-300/20 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-100 disabled:opacity-60">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>
      <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => {
          const group = getMentorshipGroup(item.segment);
          return (
            <article key={item.id} className={`group overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br ${group.accent} p-4 transition hover:-translate-y-1 hover:border-indigo-300/30`}>
              <div className="flex items-center justify-between gap-2">
                <div className="rounded-full bg-black/30 px-2 py-1 text-[10px] uppercase tracking-widest text-indigo-100">{group.label}</div>
                <div className="text-xs text-gray-300">{MEDIA_LABELS[item.media_type] || "Resource"}</div>
              </div>
              <h4 className="mt-4 text-lg font-semibold text-white">{item.title}</h4>
              {item.description && <p className="mt-2 text-sm text-gray-300">{item.description}</p>}
              <div className="mt-4 grid grid-cols-2 gap-2">
                <ResourceViewer item={item} compact />
                {item.download_url && <a href={item.download_url} download className="inline-flex items-center justify-center rounded-xl border border-white/15 bg-black/25 px-3 py-2.5 text-center text-sm font-semibold text-gray-100 transition hover:bg-white/10">Download</a>}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
