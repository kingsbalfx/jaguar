import { useEffect, useMemo, useState } from "react";
import {
  BOT_UNLIMITED_LIMIT,
  PRICING_TIERS,
  getBotTierDefaults,
  normalizeBotLimit,
} from "../../lib/pricing-config";

const ROLE_OPTIONS = ["user", "premium", "vip", "pro", "lifetime", "admin"];
const SEGMENT_FILTERS = ["all", "user", "premium", "vip", "pro", "lifetime", "admin"];
const QUALITY_OPTIONS = ["none", "basic", "standard", "premium", "vip", "pro", "elite"];
const ROLE_TO_TIER = {
  user: "FREE",
  premium: "PREMIUM",
  vip: "VIP",
  pro: "PRO",
  lifetime: "LIFETIME",
};

function getTierKeyForRole(role) {
  return ROLE_TO_TIER[String(role || "user").toLowerCase()] || "FREE";
}

function getFeatureTags(role) {
  if (role === "admin") {
    return ["Full Access", "Manage Users", "Manage Content", "Bot Control"];
  }
  const tierKey = getTierKeyForRole(role);
  const tier = PRICING_TIERS[tierKey];
  if (!tier) return [];
  const features = tier.features || {};
  const tags = [];
  if (features.botAccess) tags.push("Bot Access");
  if (features.mentorship) tags.push("Mentorship");
  if (features.lessonAccess) tags.push("Lessons");
  if (features.prioritySupport) tags.push("Priority Support");
  if (features.performanceAnalytics) tags.push("Analytics");
  return tags;
}

function formatLimit(value) {
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric >= BOT_UNLIMITED_LIMIT) return "unlimited";
  return String(value ?? 0);
}

function userWithTierDefaults(user, tierValue = user?.bot_tier || getTierKeyForRole(user?.role)) {
  const defaults = getBotTierDefaults(tierValue);
  return {
    ...user,
    bot_tier: defaults.botTier,
    bot_max_signals_per_day: defaults.botMaxSignalsPerDay,
    bot_max_concurrent_trades: defaults.botMaxConcurrentTrades,
    bot_signal_quality: defaults.botSignalQuality,
  };
}

function buildUserPayload(user) {
  return {
    id: user.id,
    role: user.role,
    lifetime: user.lifetime || false,
    botTier: user.bot_tier || getBotTierDefaults(getTierKeyForRole(user.role)).botTier,
    botMaxSignalsPerDay: normalizeBotLimit(user.bot_max_signals_per_day, 0),
    botMaxConcurrentTrades: normalizeBotLimit(user.bot_max_concurrent_trades, 0),
    botSignalQuality: user.bot_signal_quality || "none",
  };
}

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const [status, setStatus] = useState("");
  const [filter, setFilter] = useState("all");
  const [groupDraft, setGroupDraft] = useState(() => {
    const defaults = getBotTierDefaults("premium");
    return {
      role: "premium",
      bot_tier: defaults.botTier,
      bot_max_signals_per_day: defaults.botMaxSignalsPerDay,
      bot_max_concurrent_trades: defaults.botMaxConcurrentTrades,
      bot_signal_quality: defaults.botSignalQuality,
    };
  });

  useEffect(() => {
    fetchUsers();
  }, []);

  async function fetchUsers() {
    setLoading(true);
    setStatus("");
    try {
      const res = await fetch("/api/admin/users");
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load users");
      setUsers(data.users || []);
    } catch (err) {
      setStatus(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  const filteredUsers = useMemo(() => {
    if (filter === "all") return users;
    return users.filter((user) => (user.role || "user") === filter);
  }, [users, filter]);

  const groupCount = useMemo(
    () => users.filter((user) => (user.role || "user") === groupDraft.role).length,
    [users, groupDraft.role]
  );

  const patchUser = (userId, patch) => {
    setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, ...patch } : u)));
  };

  const updateUser = async (user, overrides = {}) => {
    const nextUser = { ...user, ...overrides };
    setSavingId(nextUser.id);
    setStatus("");
    try {
      const res = await fetch("/api/admin/users", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildUserPayload(nextUser)),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to update user");
      setUsers((prev) =>
        prev.map((u) => (u.id === nextUser.id ? { ...u, ...data.user } : u))
      );
      setStatus("User limits saved.");
    } catch (err) {
      setStatus(err.message || "Failed to update user");
    } finally {
      setSavingId(null);
    }
  };

  const applyRoleDefaultsToUser = (user) => {
    patchUser(user.id, userWithTierDefaults(user, user.bot_tier || getTierKeyForRole(user.role)));
  };

  const setGroupRole = (role) => {
    const defaults = getBotTierDefaults(getTierKeyForRole(role));
    setGroupDraft({
      role,
      bot_tier: defaults.botTier,
      bot_max_signals_per_day: defaults.botMaxSignalsPerDay,
      bot_max_concurrent_trades: defaults.botMaxConcurrentTrades,
      bot_signal_quality: defaults.botSignalQuality,
    });
  };

  const applyGroupLimits = async () => {
    const targets = users.filter((user) => (user.role || "user") === groupDraft.role);
    if (targets.length === 0) {
      setStatus("No users found in that group.");
      return;
    }

    setSavingId("group");
    setStatus("");
    try {
      const updated = [];
      for (const user of targets) {
        const res = await fetch("/api/admin/users", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildUserPayload({ ...user, ...groupDraft })),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || `Failed to update ${user.email}`);
        updated.push(data.user);
      }
      const byId = new Map(updated.map((user) => [user.id, user]));
      setUsers((prev) => prev.map((user) => (byId.has(user.id) ? { ...user, ...byId.get(user.id) } : user)));
      setStatus(`Saved bot limits for ${updated.length} ${groupDraft.role} user(s).`);
    } catch (err) {
      setStatus(err.message || "Failed to update group limits");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="p-6 min-h-[calc(100vh-160px)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">Users & Bot Limits</h2>
          <p className="text-sm text-gray-300 mt-1">
            Control roles, signal caps, trade limits, and bot execution quality.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {SEGMENT_FILTERS.map((seg) => (
              <option key={seg} value={seg}>
                {seg.toUpperCase()}
              </option>
            ))}
          </select>
          <button
            onClick={fetchUsers}
            className="px-3 py-2 rounded-md bg-white/10 text-sm text-white"
          >
            Refresh
          </button>
        </div>
      </div>

      {status && <div className="mt-3 text-sm text-emerald-200">{status}</div>}
      {loading && <div className="mt-3 text-sm text-gray-400">Loading users...</div>}

      <section className="mt-6 card p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-xs uppercase text-emerald-200">Group Controls</div>
            <h3 className="text-lg font-semibold text-white">Bot limits by user group</h3>
            <p className="text-sm text-gray-300 mt-1">
              Apply one limit profile to everyone in the selected group.
            </p>
          </div>
          <button
            onClick={applyGroupLimits}
            disabled={savingId === "group"}
            className="px-4 py-2 rounded-md bg-emerald-600 text-sm text-white disabled:opacity-60"
          >
            {savingId === "group" ? "Saving..." : `Apply to ${groupCount} user(s)`}
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-5">
          <label className="text-xs text-gray-400">
            Group
            <select
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              value={groupDraft.role}
              onChange={(e) => setGroupRole(e.target.value)}
            >
              {ROLE_OPTIONS.filter((role) => role !== "admin").map((role) => (
                <option key={role} value={role}>
                  {role.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-400">
            Tier
            <select
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              value={groupDraft.bot_tier}
              onChange={(e) => setGroupDraft(userWithTierDefaults(groupDraft, e.target.value))}
            >
              {Object.values(PRICING_TIERS).map((tier) => (
                <option key={tier.id} value={tier.id}>
                  {tier.displayName}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-400">
            Signals/day
            <input
              type="number"
              min="0"
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              value={groupDraft.bot_max_signals_per_day}
              onChange={(e) =>
                setGroupDraft((prev) => ({
                  ...prev,
                  bot_max_signals_per_day: normalizeBotLimit(e.target.value, 0),
                }))
              }
            />
          </label>
          <label className="text-xs text-gray-400">
            Max trades
            <input
              type="number"
              min="0"
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              value={groupDraft.bot_max_concurrent_trades}
              onChange={(e) =>
                setGroupDraft((prev) => ({
                  ...prev,
                  bot_max_concurrent_trades: normalizeBotLimit(e.target.value, 0),
                }))
              }
            />
          </label>
          <label className="text-xs text-gray-400">
            Quality
            <select
              className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              value={groupDraft.bot_signal_quality}
              onChange={(e) => setGroupDraft((prev) => ({ ...prev, bot_signal_quality: e.target.value }))}
            >
              {QUALITY_OPTIONS.map((quality) => (
                <option key={quality} value={quality}>
                  {quality.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <div className="mt-6 space-y-4">
        {filteredUsers.map((user) => {
          const tags = getFeatureTags(user.role || "user");
          return (
            <div key={user.id} className="card p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="text-lg font-semibold text-white">
                    {user.username || user.name || "Unnamed User"}
                  </div>
                  <div className="text-xs text-gray-400">{user.email}</div>
                  <div className="mt-2 text-xs text-gray-400">
                    Plan: <span className="text-white">{(user.plan || "user").toUpperCase()}</span>
                    {" | "}Status:{" "}
                    <span className="text-white">{(user.planStatus || "none").toUpperCase()}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <span className="text-xs px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-200">
                      Signals/day: {formatLimit(user.bot_max_signals_per_day)}
                    </span>
                    <span className="text-xs px-2 py-1 rounded-md bg-cyan-500/10 text-cyan-200">
                      Max trades: {formatLimit(user.bot_max_concurrent_trades)}
                    </span>
                    <span className="text-xs px-2 py-1 rounded-md bg-white/10 text-gray-200">
                      Quality: {(user.bot_signal_quality || "none").toUpperCase()}
                    </span>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                  <label className="text-xs text-gray-400">
                    Role
                    <select
                      className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.role || "user"}
                      onChange={(e) => {
                        const next = e.target.value;
                        const defaults = getBotTierDefaults(getTierKeyForRole(next));
                        patchUser(user.id, {
                          role: next,
                          bot_tier: defaults.botTier,
                          bot_max_signals_per_day: defaults.botMaxSignalsPerDay,
                          bot_max_concurrent_trades: defaults.botMaxConcurrentTrades,
                          bot_signal_quality: defaults.botSignalQuality,
                        });
                      }}
                    >
                      {ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>
                          {role.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-gray-400">
                    Bot tier
                    <select
                      className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.bot_tier || getBotTierDefaults(getTierKeyForRole(user.role)).botTier}
                      onChange={(e) => patchUser(user.id, userWithTierDefaults(user, e.target.value))}
                    >
                      {Object.values(PRICING_TIERS).map((tier) => (
                        <option key={tier.id} value={tier.id}>
                          {tier.displayName}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-xs text-gray-400">
                    Signals/day
                    <input
                      type="number"
                      min="0"
                      className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.bot_max_signals_per_day ?? 0}
                      onChange={(e) =>
                        patchUser(user.id, {
                          bot_max_signals_per_day: normalizeBotLimit(e.target.value, 0),
                        })
                      }
                    />
                  </label>
                  <label className="text-xs text-gray-400">
                    Max trades
                    <input
                      type="number"
                      min="0"
                      className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.bot_max_concurrent_trades ?? 0}
                      onChange={(e) =>
                        patchUser(user.id, {
                          bot_max_concurrent_trades: normalizeBotLimit(e.target.value, 0),
                        })
                      }
                    />
                  </label>
                  <label className="text-xs text-gray-400">
                    Quality
                    <select
                      className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.bot_signal_quality || "none"}
                      onChange={(e) => patchUser(user.id, { bot_signal_quality: e.target.value })}
                    >
                      {QUALITY_OPTIONS.map((quality) => (
                        <option key={quality} value={quality}>
                          {quality.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="flex items-end gap-2">
                    <button
                      onClick={() => applyRoleDefaultsToUser(user)}
                      className="px-3 py-2 rounded-md bg-white/10 text-xs text-white"
                    >
                      Tier defaults
                    </button>
                    <button
                      onClick={() => updateUser(user)}
                      disabled={savingId === user.id}
                      className="px-4 py-2 rounded-md bg-emerald-600 text-white text-sm disabled:opacity-60"
                    >
                      {savingId === user.id ? "Saving..." : "Save"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {tags.length === 0 && (
                  <span className="text-xs text-gray-400">No active features.</span>
                )}
                {tags.map((tag) => (
                  <span key={tag} className="text-xs px-2 py-1 rounded-md bg-white/10 text-gray-200">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
        {!loading && filteredUsers.length === 0 && (
          <div className="text-sm text-gray-400">No users found for this segment.</div>
        )}
      </div>
    </div>
  );
}
