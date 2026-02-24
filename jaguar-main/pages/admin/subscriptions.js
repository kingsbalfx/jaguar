export default function Subs() {
  const tiers = ["free", "premium", "vip", "pro", "lifetime"];
  return (
    <div className="p-6 space-y-4">
      <h2 className="text-2xl font-bold">Subscription Management</h2>
      <p className="text-gray-300 text-sm">
        Manage all tiers (free, premium, vip, pro, lifetime). This is a placeholder until
        automated billing actions are wired in.
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {tiers.map((tier) => (
          <div key={tier} className="rounded-lg bg-white/5 p-3">
            <div className="text-xs text-gray-400 uppercase">Tier</div>
            <div className="text-lg font-semibold">{tier.toUpperCase()}</div>
            <div className="text-xs text-gray-400 mt-1">Active subscribers: —</div>
          </div>
        ))}
      </div>
    </div>
  );
}
