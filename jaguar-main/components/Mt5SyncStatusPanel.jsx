import { useCallback, useEffect, useState } from "react";
import FeedbackMessage from "./FeedbackMessage";

const DEFAULT_LOOKBACK = 120;

function statusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "success" || value === "ready" || value === "deployed") return "text-emerald-200";
  if (value === "partial" || value === "provisioning" || value === "pending" || value === "idle") return "text-amber-200";
  if (value === "error" || value === "failed") return "text-red-200";
  return "text-gray-300";
}

/**
 * Sync control + health panel. Users link their own MT5 account and trigger a sync;
 * admins get the same view across every account (/api/admin/mt5-links).
 */
export default function Mt5SyncStatusPanel({ admin = false, showLinkForm = true }) {
  const endpoint = admin ? "/api/admin/mt5-links" : "/api/user/mt5-sync";
  const [state, setState] = useState({
    loading: true,
    error: "",
    setupRequired: false,
    bridge: null,
    links: [],
    runs: [],
    totals: null,
  });
  const [form, setForm] = useState({ login: "", server: "", password: "", label: "", lookbackDays: DEFAULT_LOOKBACK });
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState({ type: "", message: "" });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await fetch(endpoint);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load MT5 sync status.");
      setState({
        loading: false,
        error: "",
        setupRequired: Boolean(data.setupRequired),
        bridge: data.bridge || null,
        links: data.links || [],
        runs: data.runs || [],
        totals: data.totals || null,
      });
    } catch (err) {
      setState((prev) => ({ ...prev, loading: false, error: err.message || "Failed to load MT5 sync status." }));
    }
  }, [endpoint]);

  useEffect(() => {
    load();
  }, [load]);

  const request = async (url, options = {}) => {
    const res = await fetch(url, {
      ...options,
      headers: { "content-type": "application/json", ...(options.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && res.status !== 207) throw new Error(data?.error || "Request failed.");
    return data;
  };

  const linkAccount = async (event) => {
    if (event) event.preventDefault();
    setBusy("link");
    setNotice({ type: "", message: "" });
    try {
      const data = await request("/api/user/mt5-sync", {
        method: "POST",
        body: JSON.stringify({
          login: form.login.trim(),
          server: form.server.trim(),
          password: form.password,
          label: form.label.trim() || undefined,
          lookbackDays: Number(form.lookbackDays) || DEFAULT_LOOKBACK,
        }),
      });
      setNotice({
        type: data?.status === "success" ? "success" : "warning",
        message:
          data?.status === "success"
            ? `Synced ${data.tradesInserted || 0} new trade(s) from ${data.dealsReceived || 0} deals.`
            : data?.error || data?.status || "Sync finished with warnings.",
      });
      setForm((prev) => ({ ...prev, password: "" }));
      await load();
    } catch (err) {
      setNotice({ type: "error", message: err.message || "Failed to link account." });
    } finally {
      setBusy("");
    }
  };

  const syncNow = async (link) => {
    setBusy(link.id);
    setNotice({ type: "", message: "" });
    try {
      const data = admin
        ? await request("/api/admin/mt5-links", { method: "POST", body: JSON.stringify({ id: link.id }) })
        : await request("/api/user/mt5-sync", { method: "POST", body: JSON.stringify({ linkId: link.id }) });
      setNotice({
        type: data?.ok ? "success" : "warning",
        message: data?.ok
          ? `Synced ${link.label || link.login}: ${data.tradesInserted || 0} new, ${data.tradesUpdated || 0} updated.`
          : data?.error || "Sync finished with warnings.",
      });
      await load();
    } catch (err) {
      setNotice({ type: "error", message: err.message || "Sync failed." });
    } finally {
      setBusy("");
    }
  };

  const toggleSync = async (link) => {
    setBusy(link.id);
    try {
      if (admin) {
        await request("/api/admin/mt5-links", {
          method: "PATCH",
          body: JSON.stringify({ id: link.id, sync_enabled: !link.sync_enabled }),
        });
      } else {
        await request("/api/user/mt5-sync", {
          method: "POST",
          body: JSON.stringify({ linkId: link.id, syncEnabled: !link.sync_enabled }),
        });
      }
      await load();
    } catch (err) {
      setNotice({ type: "error", message: err.message || "Failed to update the link." });
    } finally {
      setBusy("");
    }
  };

  const removeLink = async (link) => {
    setBusy(link.id);
    try {
      if (admin) {
        await request("/api/admin/mt5-links", { method: "DELETE", body: JSON.stringify({ id: link.id }) });
      } else {
        await request("/api/user/mt5-sync", { method: "DELETE", body: JSON.stringify({ linkId: link.id }) });
      }
      setNotice({ type: "success", message: `Removed ${link.label || link.login} and its stored trades.` });
      await load();
    } catch (err) {
      setNotice({ type: "error", message: err.message || "Failed to remove the link." });
    } finally {
      setBusy("");
    }
  };

  const inputClass = "mt-1 w-full rounded-md border border-white/10 bg-black/40 px-2 py-2 text-sm text-white";
  const bridgeReady = Boolean(state.bridge?.configured);

  return (
    <section className="glass-panel rounded-lg p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs text-emerald-200">{admin ? "All MT5 Accounts" : "My MT5 Account"}</div>
          <h3 className="text-lg font-semibold text-white">Trade Sync</h3>
          <p className="text-sm text-gray-400">
            Closed trades are pulled from the cloud bridge, then stored for history and pair analytics.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="rounded-md border border-white/10 px-3 py-2 text-xs text-gray-200 hover:bg-white/10"
        >
          Refresh
        </button>
      </div>

      <div className="mt-3 rounded-md border border-white/10 bg-black/30 p-3 text-xs">
        <div className={bridgeReady ? "text-emerald-200" : "text-amber-200"}>
          Bridge: {state.bridge?.provider || "not configured"}
          {bridgeReady ? " — ready" : ` — ${state.bridge?.reason || "set bridge credentials in the environment"}`}
        </div>
        {state.bridge?.providers && (
          <div className="mt-1 text-gray-400">
            {state.bridge.providers
              .map((provider) => `${provider.provider}${provider.configured ? " ✓" : " ✗"}`)
              .join("  ·  ")}
          </div>
        )}
        {state.totals && (
          <div className="mt-1 text-gray-400">
            {state.totals.links || 0} link(s) · {state.totals.totalSyncedDeals || 0} deals synced ·{" "}
            {state.totals.errors || 0} error(s)
          </div>
        )}
      </div>

      <FeedbackMessage message={notice.message} type={notice.type || "info"} />
      <FeedbackMessage message={state.error} type="error" />
      {state.setupRequired && (
        <p className="mt-2 text-xs text-amber-200">
          Apply sql/2026-10-13_mt5_trade_sync.sql to enable trade history storage.
        </p>
      )}
      {state.loading && <div className="mt-3 text-sm text-gray-400">Loading sync status...</div>}

      {showLinkForm && !admin && (
        <form onSubmit={linkAccount} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-gray-400">
            MT5 login
            <input
              value={form.login}
              onChange={(event) => setForm((prev) => ({ ...prev, login: event.target.value }))}
              placeholder="12345678"
              className={inputClass}
              required
            />
          </label>
          <label className="text-xs text-gray-400">
            Server
            <input
              value={form.server}
              onChange={(event) => setForm((prev) => ({ ...prev, server: event.target.value }))}
              placeholder="Exness-MT5Real"
              className={inputClass}
              required
            />
          </label>
          <label className="text-xs text-gray-400">
            Investor (read-only) password
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder="never returned by the API"
              className={inputClass}
              required
            />
          </label>
          <label className="text-xs text-gray-400">
            Label
            <input
              value={form.label}
              onChange={(event) => setForm((prev) => ({ ...prev, label: event.target.value }))}
              placeholder="Live / Prop"
              className={inputClass}
            />
          </label>
          <label className="text-xs text-gray-400">
            Lookback days
            <input
              type="number"
              min="1"
              max="3650"
              value={form.lookbackDays}
              onChange={(event) => setForm((prev) => ({ ...prev, lookbackDays: event.target.value }))}
              className={inputClass}
            />
          </label>
          <div className="flex items-end lg:col-span-3">
            <button
              type="submit"
              disabled={busy === "link"}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {busy === "link" ? "Linking..." : "Link & sync now"}
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="text-gray-400">
              <th className="px-2 py-1">Account</th>
              {admin && <th className="px-2 py-1">User</th>}
              <th className="px-2 py-1">Provider</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1 text-right">Deals</th>
              <th className="px-2 py-1">Last sync</th>
              <th className="px-2 py-1">Cursor</th>
              <th className="px-2 py-1 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {state.links.map((link) => (
              <tr key={link.id} className="border-t border-white/5 align-top">
                <td className="px-2 py-2">
                  <div className="font-semibold text-white">{link.label || link.login}</div>
                  <div className="text-xs text-gray-400">
                    {link.login} · {link.server}
                  </div>
                </td>
                {admin && <td className="px-2 py-2 text-xs text-gray-400">{link.email || link.user_id}</td>}
                <td className="px-2 py-2 text-xs text-gray-300">
                  {link.provider || "-"}
                  {link.bridge_account_id && (
                    <div className="text-[11px] text-gray-500">{link.bridge_account_id}</div>
                  )}
                </td>
                <td className="px-2 py-2 text-xs">
                  <div className={statusTone(link.sync_status)}>{link.sync_status || "idle"}</div>
                  <div className="text-[11px] text-gray-500">
                    {link.sync_enabled ? "enabled" : "paused"} · {link.provisioning_status || "pending"}
                  </div>
                  {link.sync_error && <div className="mt-1 max-w-[220px] text-[11px] text-red-200">{link.sync_error}</div>}
                  {link.provisioning_error && (
                    <div className="mt-1 max-w-[220px] text-[11px] text-amber-200">{link.provisioning_error}</div>
                  )}
                </td>
                <td className="px-2 py-2 text-right text-xs text-gray-300">
                  {link.total_synced_deals || 0}
                  <div className="text-[11px] text-gray-500">last {link.last_sync_deals || 0}</div>
                </td>
                <td className="px-2 py-2 text-xs text-gray-400">
                  {link.last_synced_at ? new Date(link.last_synced_at).toLocaleString() : "never"}
                </td>
                <td className="px-2 py-2 text-xs text-gray-400">
                  {link.last_deal_time ? new Date(link.last_deal_time).toLocaleDateString() : "-"}
                </td>
                <td className="px-2 py-2 text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => syncNow(link)}
                      disabled={busy === link.id}
                      className="rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/10 disabled:opacity-40"
                    >
                      Sync
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleSync(link)}
                      disabled={busy === link.id}
                      className="rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/10 disabled:opacity-40"
                    >
                      {link.sync_enabled ? "Pause" : "Resume"}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeLink(link)}
                      disabled={busy === link.id}
                      className="rounded-md border border-white/10 px-2 py-1 text-xs text-red-200 hover:bg-white/10 disabled:opacity-40"
                    >
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!state.loading && state.links.length === 0 && (
              <tr>
                <td className="px-2 py-3 text-gray-400" colSpan={admin ? 8 : 7}>
                  No MT5 account linked yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {state.runs.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-semibold text-white">Recent sync runs</h4>
          <div className="mt-2 overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="text-gray-400">
                  <th className="px-2 py-1">When</th>
                  <th className="px-2 py-1">Account</th>
                  <th className="px-2 py-1">Trigger</th>
                  <th className="px-2 py-1">Status</th>
                  <th className="px-2 py-1 text-right">Deals</th>
                  <th className="px-2 py-1 text-right">New</th>
                  <th className="px-2 py-1 text-right">Updated</th>
                  <th className="px-2 py-1 text-right">Duration</th>
                  <th className="px-2 py-1">Error</th>
                </tr>
              </thead>
              <tbody>
                {state.runs.map((run) => (
                  <tr key={run.id} className="border-t border-white/5">
                    <td className="px-2 py-1 text-gray-400">
                      {run.created_at ? new Date(run.created_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-2 py-1">{run.account_login || "-"}</td>
                    <td className="px-2 py-1 text-gray-400">{run.trigger || "-"}</td>
                    <td className={`px-2 py-1 ${statusTone(run.status)}`}>{run.status}</td>
                    <td className="px-2 py-1 text-right">{run.deals_received || 0}</td>
                    <td className="px-2 py-1 text-right">{run.trades_inserted || 0}</td>
                    <td className="px-2 py-1 text-right">{run.trades_updated || 0}</td>
                    <td className="px-2 py-1 text-right text-gray-400">
                      {run.duration_ms ? `${run.duration_ms}ms` : "-"}
                    </td>
                    <td className="max-w-[220px] truncate px-2 py-1 text-red-200">{run.error || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
