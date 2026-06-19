import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const unread = useMemo(() => items.filter((item) => !item.read_at).length, [items]);

  const load = async () => {
    try {
      const response = await fetch("/api/notifications", { cache: "no-store" });
      if (response.status === 401) {
        setItems([]);
        return;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to load notifications.");
      setItems(data.notifications || []);
      setError("");
    } catch (err) {
      setError(err.message || "Unable to load notifications.");
    }
  };

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 45000);
    return () => window.clearInterval(timer);
  }, []);

  const markRead = async (id = "") => {
    await fetch("/api/notifications", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    }).catch(() => {});
    load();
  };

  if (!items.length && !error) return null;

  return (
    <div className="fixed right-4 top-24 z-[90] text-white">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-full border border-emerald-300/30 bg-slate-950/95 px-4 py-3 text-sm font-semibold shadow-2xl backdrop-blur hover:bg-slate-900"
      >
        Notifications
        {unread > 0 && <span className="absolute -right-2 -top-2 rounded-full bg-red-500 px-2 py-0.5 text-xs">{unread}</span>}
      </button>
      {open && (
        <div className="mt-2 w-[min(92vw,360px)] rounded-2xl border border-white/10 bg-slate-950/98 p-3 shadow-2xl backdrop-blur">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-bold">KINGSBALFX Alerts</div>
            {unread > 0 && <button type="button" onClick={() => markRead()} className="text-xs text-emerald-300">Mark all read</button>}
          </div>
          {error && <div className="rounded bg-red-500/10 p-2 text-xs text-red-200">{error}</div>}
          <div className="max-h-96 space-y-2 overflow-auto">
            {items.map((item) => (
              <div key={item.id} className={`rounded-xl border p-3 text-sm ${item.read_at ? "border-white/10 bg-white/5" : "border-emerald-300/30 bg-emerald-500/10"}`}>
                <div className="font-semibold">{item.title}</div>
                <div className="mt-1 text-xs text-gray-300">{item.body}</div>
                <div className="mt-2 flex items-center justify-between gap-2 text-xs">
                  <span className="text-gray-500">{new Date(item.created_at).toLocaleString()}</span>
                  <span className="flex gap-2">
                    {item.link && (
                      <Link href={item.link}>
                        <a onClick={() => markRead(item.id)} className="text-emerald-300">Open</a>
                      </Link>
                    )}
                    {!item.read_at && <button type="button" onClick={() => markRead(item.id)} className="text-gray-300">Read</button>}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
