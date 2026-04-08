import { useCallback, useEffect, useState } from "react";

function money(value, currency = "USD") {
  const numeric = Number(value || 0);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${numeric.toFixed(2)} ${currency || ""}`.trim();
  }
}

export default function AccountFloatPanel({ admin = false }) {
  const [state, setState] = useState({ loading: true, error: "", accounts: [], totals: null });

  const loadFloat = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await fetch(`/api/bot/account-float${admin ? "?scope=all" : ""}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load account float.");
      setState({
        loading: false,
        error: "",
        accounts: data.accounts || [],
        totals: data.totals || null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err.message || "Failed to load account float.",
      }));
    }
  }, [admin]);

  useEffect(() => {
    loadFloat();
    const timer = setInterval(loadFloat, 30000);
    return () => clearInterval(timer);
  }, [loadFloat]);

  const totalCurrency = state.accounts[0]?.currency || "USD";
  const totalFloat = state.totals?.floatingProfit || 0;
  const floatClass = totalFloat >= 0 ? "text-emerald-200" : "text-red-200";

  return (
    <section className="glass-panel rounded-lg p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs text-emerald-200">{admin ? "All MT5 Accounts" : "My MT5 Account"}</div>
          <h3 className="text-lg font-semibold text-white">Floating Money</h3>
          <p className="text-sm text-gray-400">
            Live equity, balance, floating P/L, and open trades.
          </p>
        </div>
        <button
          type="button"
          onClick={loadFloat}
          className="rounded-md border border-white/10 px-3 py-2 text-xs text-gray-200 hover:bg-white/10"
        >
          Refresh
        </button>
      </div>

      {state.error && <div className="mt-3 text-sm text-red-300">{state.error}</div>}
      {state.loading && <div className="mt-3 text-sm text-gray-400">Loading account float...</div>}

      {!state.loading && !state.error && (
        <>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="rounded-md border border-white/10 bg-black/30 p-3">
              <div className="text-xs text-gray-400">Floating P/L</div>
              <div className={`text-2xl font-semibold ${floatClass}`}>
                {money(totalFloat, totalCurrency)}
              </div>
            </div>
            <div className="rounded-md border border-white/10 bg-black/30 p-3">
              <div className="text-xs text-gray-400">Balance</div>
              <div className="text-xl font-semibold text-white">
                {money(state.totals?.balance || 0, totalCurrency)}
              </div>
            </div>
            <div className="rounded-md border border-white/10 bg-black/30 p-3">
              <div className="text-xs text-gray-400">Equity</div>
              <div className="text-xl font-semibold text-white">
                {money(state.totals?.equity || 0, totalCurrency)}
              </div>
            </div>
            <div className="rounded-md border border-white/10 bg-black/30 p-3">
              <div className="text-xs text-gray-400">Accounts</div>
              <div className="text-xl font-semibold text-white">{state.totals?.count || 0}</div>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="text-gray-400">
                  <th className="px-2 py-1">Login</th>
                  {admin && <th className="px-2 py-1">User</th>}
                  <th className="px-2 py-1">Balance</th>
                  <th className="px-2 py-1">Equity</th>
                  <th className="px-2 py-1">Float</th>
                  <th className="px-2 py-1">Open</th>
                  <th className="px-2 py-1">Scan</th>
                  <th className="px-2 py-1">Updated</th>
                </tr>
              </thead>
              <tbody>
                {state.accounts.map((account) => {
                  const accountFloat = Number(account.floating_profit || 0);
                  const assetScan = account.asset_scan || {};
                  return (
                    <tr key={account.id || account.bot_id || account.account_login} className="border-t border-white/5">
                      <td className="px-2 py-2">{account.account_login || "-"}</td>
                      {admin && <td className="px-2 py-2">{account.user_email || account.user_id || "-"}</td>}
                      <td className="px-2 py-2">{money(account.balance || 0, account.currency || totalCurrency)}</td>
                      <td className="px-2 py-2">{money(account.equity || 0, account.currency || totalCurrency)}</td>
                      <td className={`px-2 py-2 ${accountFloat >= 0 ? "text-emerald-200" : "text-red-200"}`}>
                        {money(accountFloat, account.currency || totalCurrency)}
                      </td>
                      <td className="px-2 py-2">{account.open_positions || 0}</td>
                      <td className="px-2 py-2 text-xs text-gray-300">
                        F:{assetScan.forex || 0} M:{assetScan.metals || 0} C:{assetScan.crypto || 0}
                      </td>
                      <td className="px-2 py-2 text-xs text-gray-400">
                        {account.created_at ? new Date(account.created_at).toLocaleString() : "-"}
                      </td>
                    </tr>
                  );
                })}
                {state.accounts.length === 0 && (
                  <tr>
                    <td className="px-2 py-3 text-gray-400" colSpan={admin ? 8 : 7}>
                      No account float snapshot yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
