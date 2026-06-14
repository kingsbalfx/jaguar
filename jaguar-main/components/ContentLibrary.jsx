import { useEffect, useState } from "react";
import { getMentorshipGroup } from "../lib/mentorship-groups";

const MEDIA_LABELS = { video: "Watch lesson", audio: "Listen", pdf: "Open workbook", text: "Read lesson", link: "Open resource" };

export default function ContentLibrary() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/content/items")
      .then((res) => res.json())
      .then((data) => data?.items ? setItems(data.items) : setError(data?.error || "Unable to load content."))
      .catch(() => setError("Unable to load content."));
  }, []);

  if (error) return <div className="mt-6 text-sm text-red-300">{error}</div>;
  if (!items.length) return (
    <div className="mt-6 rounded-2xl border border-dashed border-indigo-300/20 bg-indigo-500/5 p-8 text-center text-gray-300">
      <div className="text-lg font-semibold text-white">Your learning library is ready</div>
      <div className="mt-2 text-sm">New lessons and resources published for your group will appear here.</div>
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
        <div className="rounded-full border border-emerald-300/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{items.length} resources available</div>
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
              {item.media_type === "text" && <div className="mt-4 max-h-56 overflow-auto whitespace-pre-wrap rounded-xl bg-black/25 p-3 text-sm text-gray-200">{item.body}</div>}
              {item.media_type === "video" && item.public_url && <video src={item.public_url} controls className="mt-4 aspect-video w-full rounded-xl bg-black" />}
              {item.media_type === "audio" && item.public_url && <audio src={item.public_url} controls className="mt-4 w-full" />}
              {item.media_type === "pdf" && item.public_url && <a href={item.public_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Open workbook</a>}
              {item.media_type === "link" && item.media_url && <a href={item.media_url} target="_blank" rel="noreferrer" className="mt-4 inline-flex rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white">Open resource</a>}
            </article>
          );
        })}
      </div>
    </section>
  );
}
