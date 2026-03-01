import MT5SubmissionForm from "./MT5SubmissionForm";

export default function BotAccessPanel({ tier, isActive }) {
  const features = tier?.features || {};
  const botAccess = Boolean(features.botAccess);
  const maxSignals = features.maxSignalsPerDay ?? "N/A";
  const maxTrades = features.maxConcurrentTrades ?? "N/A";
  const signalQuality = features.signalQuality || "standard";

  return (
    <div className="glass-panel rounded-2xl p-5">
      <div className="text-xs uppercase tracking-widest text-emerald-200">Bot Trading Access</div>
      <h3 className="text-lg font-semibold mt-1">Automated MT5 Signals</h3>
      <p className="text-sm text-gray-300 mt-1">
        {botAccess
          ? "Your plan includes bot trading access. Submit your MT5 credentials to activate."
          : "Bot trading is not available on this plan. Upgrade to unlock automated trading."}
      </p>

      <div className="mt-3 grid sm:grid-cols-3 gap-3 text-xs text-gray-300">
        <div className="bg-black/30 rounded-lg p-3 border border-white/5">
          <div className="text-gray-400">Signal quality</div>
          <div className="text-white font-semibold">{signalQuality}</div>
        </div>
        <div className="bg-black/30 rounded-lg p-3 border border-white/5">
          <div className="text-gray-400">Signals/day</div>
          <div className="text-white font-semibold">{String(maxSignals)}</div>
        </div>
        <div className="bg-black/30 rounded-lg p-3 border border-white/5">
          <div className="text-gray-400">Max trades</div>
          <div className="text-white font-semibold">{String(maxTrades)}</div>
        </div>
      </div>

      <div className="mt-4">
        {botAccess && isActive ? (
          <MT5SubmissionForm />
        ) : (
          <div className="text-sm text-yellow-300">
            Activate your subscription to enable MT5 submission.
          </div>
        )}
      </div>
    </div>
  );
}
