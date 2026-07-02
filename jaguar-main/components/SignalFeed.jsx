import { useEffect, useState } from "react";
import FeedbackMessage from "./FeedbackMessage";

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "-" : value;
}

export default function SignalFeed() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const response = await fetch("/api/user/signals?limit=25", { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Unable to load signals.");
        if (alive) {
          setSignals(data.signals || []);
          setMessage(data.missingTable ? "Signal delivery SQL is not installed yet." : "");
        }
      } catch (error) {
        if (alive) setMessage(error.message || "Unable to load signals.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section id="signals" className="rounded-3xl border border-white/10 bg-slate-950/75 p-5 shadow-2xl backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.24em] text-emerald-200">Signal Desk</div>
          <h2 className="mt-1 text-xl font-bold text-white">Your delivered signals</h2>
          <p className="mt-1 text-sm text-gray-300">Signals are shown according to your active tier and daily delivery limit.</p>
        </div>
        <div className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200">
          {loading ? "Loading" : `${signals.length} recent`}
        </div>
      </div>

      <FeedbackMessage message={message} type={/unable|failed|not installed/i.test(message) ? "error" : "info"} />

      <div className="mt-4 grid gap-3">
        {signals.map((signal) => {
          const direction = String(signal.direction || "").toUpperCase();
          const sideClass = direction === "BUY" ? "text-emerald-200 bg-emerald-500/10" : "text-red-200 bg-red-500/10";
          return (
            <article key={signal.id} className="rounded-2xl border border-white/10 bg-black/30 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-3 py-1 text-xs font-black ${sideClass}`}>{direction || "SIGNAL"}</span>
                    <span className="text-lg font-black text-white">{signal.symbol || "Market"}</span>
                    <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-gray-300">{String(signal.plan || "").toUpperCase()}</span>
                  </div>
                  <div className="mt-2 grid gap-2 text-sm text-gray-200 sm:grid-cols-4">
                    <span>Entry: <strong>{valueOrDash(signal.entry_price)}</strong></span>
                    <span>SL: <strong className="text-red-200">{valueOrDash(signal.stop_loss)}</strong></span>
                    <span>TP: <strong className="text-emerald-200">{valueOrDash(signal.take_profit)}</strong></span>
                    <span>Confidence: <strong>{valueOrDash(signal.confidence)}</strong></span>
                  </div>
                  {signal.reason?.note && <p className="mt-2 text-sm text-gray-400">{signal.reason.note}</p>}
                </div>
                <div className="text-right text-xs text-gray-400">
                  <div>{signal.deliveredAt ? new Date(signal.deliveredAt).toLocaleString() : ""}</div>
                  <div className="mt-1">Daily cap: {signal.dailyLimit}</div>
                </div>
              </div>
            </article>
          );
        })}
        {!loading && signals.length === 0 && !message && (
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4 text-sm text-gray-400">
            No signals have been delivered to your tier yet.
          </div>
        )}
      </div>
    </section>
  );
}
