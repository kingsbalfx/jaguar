import { useEffect, useMemo, useState } from "react";
import { PRICING_TIERS } from "../../lib/pricing-config";

const ROLE_OPTIONS = ["user", "premium", "vip", "pro", "lifetime", "admin"];
const SEGMENT_FILTERS = ["all", "user", "premium", "vip", "pro", "lifetime", "admin"];
const ROLE_TO_TIER = {
  user: "FREE",
  premium: "PREMIUM",
  vip: "VIP",
  pro: "PRO",
  lifetime: "LIFETIME",
};

function getFeatureTags(role) {
  if (role === "admin") {
    return ["Full Access", "Manage Users", "Manage Content", "Bot Control"];
  }
  const tierKey = ROLE_TO_TIER[role] || "FREE";
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

export default function Users() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const [status, setStatus] = useState("");
  const [filter, setFilter] = useState("all");

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

  const updateUser = async (user) => {
    setSavingId(user.id);
    setStatus("");
    try {
      const res = await fetch("/api/admin/users", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: user.id,
          role: user.role,
          lifetime: user.lifetime || false,
          botTier: user.bot_tier,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to update user");
      setUsers((prev) =>
        prev.map((u) => (u.id === user.id ? { ...u, ...data.user } : u))
      );
      setStatus("User updated successfully.");
    } catch (err) {
      setStatus(err.message || "Failed to update user");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="p-6 min-h-[calc(100vh-160px)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">Users & Segmentation</h2>
          <p className="text-sm text-gray-300 mt-1">
            Review subscribers, update roles, and verify plan access.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="rounded bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
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
            className="px-3 py-2 rounded bg-white/10 text-sm text-white"
          >
            Refresh
          </button>
        </div>
      </div>

      {status && <div className="mt-3 text-sm text-emerald-200">{status}</div>}
      {loading && <div className="mt-3 text-sm text-gray-400">Loading users...</div>}

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
                    {"  "}• Status:{" "}
                    <span className="text-white">{(user.planStatus || "none").toUpperCase()}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Role</label>
                    <select
                      className="rounded bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
                      value={user.role || "user"}
                      onChange={(e) => {
                        const next = e.target.value;
                        setUsers((prev) =>
                          prev.map((u) => (u.id === user.id ? { ...u, role: next } : u))
                        );
                      }}
                    >
                      {ROLE_OPTIONS.map((role) => (
                        <option key={role} value={role}>
                          {role.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => updateUser(user)}
                    disabled={savingId === user.id}
                    className="mt-5 px-4 py-2 rounded bg-indigo-600 text-white text-sm disabled:opacity-60"
                  >
                    {savingId === user.id ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {tags.length === 0 && (
                  <span className="text-xs text-gray-400">No active features.</span>
                )}
                {tags.map((tag) => (
                  <span key={tag} className="text-xs px-2 py-1 rounded-full bg-white/10 text-gray-200">
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
