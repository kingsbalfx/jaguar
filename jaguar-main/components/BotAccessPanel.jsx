import MT5SubmissionForm from "./MT5SubmissionForm";
import AccountFloatPanel from "./AccountFloatPanel";
import TradingProfilePanel from "./TradingProfilePanel";
import RiskDisclaimer from "./RiskDisclaimer";

export default function BotAccessPanel({ tier, isActive }) {
  const features = tier?.features || {};
  const botAccess = Boolean(features.botAccess || features.privateTestingOnly);

  return (
    <div className="glass-panel rounded-2xl p-5">
      <div className="text-xs uppercase tracking-widest text-emerald-200">Controlled Testing</div>
      <h3 className="text-lg font-semibold mt-1">Private Bot Testing / Account Review</h3>
      <p className="text-sm text-gray-300 mt-1">
        {botAccess
          ? "Bot-related tools are under controlled testing. Access is not a guarantee of profit."
          : "Bot testing is not included in this plan."}
      </p>
      <div className="mt-4"><RiskDisclaimer /></div>

      <div className="mt-4">
        {botAccess && isActive ? (
          <div className="space-y-4">
            <AccountFloatPanel />
            <TradingProfilePanel />
            <MT5SubmissionForm />
          </div>
        ) : (
          <div className="text-sm text-yellow-300">
            {isActive ? "Bot testing is not included in this plan." : "Activate your subscription to request a review."}
          </div>
        )}
      </div>
    </div>
  );
}
