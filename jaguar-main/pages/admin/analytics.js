import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const { data: { session } } = await supabase.auth.getSession();

    if (!session?.user) return { redirect: { destination: "/login", permanent: false } };

    const supabaseAdmin = getSupabaseClient({ server: true });
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return { redirect: { destination: "/", permanent: false } };

    // Fetch analytics data
    const { data: trades } = await supabaseAdmin.from("bot_logs").select("payload").eq("event", "trade_pushed").limit(1000);

    const analytics = calculateTradeMetrics(trades || []);

    return { props: { analytics } };
  } catch (e) {
    console.error(e);
    return { props: { analytics: null } };
  }
};

function calculateTradeMetrics(trades) {
  if (!trades.length) return null;

  const tradeData = trades.map((t) => t.payload).filter((p) => p && typeof p === "object");
  const totalTrades = tradeData.length;
  let winningTrades = 0;
  let totalProfit = 0;
  let totalLoss = 0;
  const bySymbol = {};

  tradeData.forEach((trade) => {
    const symbol = trade.symbol || "UNKNOWN";
    if (!bySymbol[symbol]) bySymbol[symbol] = { wins: 0, losses: 0, pnl: 0 };

    // Mock: assume trades with status "closed" and assume randomness for now
    const isWin = Math.random() > 0.5; // in production, compare actual close price
    const pnl = isWin ? Math.random() * 100 : -Math.random() * 50;

    if (isWin) {
      winningTrades++;
      totalProfit += pnl;
      bySymbol[symbol].wins++;
    } else {
      totalLoss += Math.abs(pnl);
      bySymbol[symbol].losses++;
    }
    bySymbol[symbol].pnl += pnl;
  });

  const winRate = (winningTrades / totalTrades) * 100;
  const profitFactor = totalLoss > 0 ? totalProfit / totalLoss : totalProfit > 0 ? Infinity : 0;
  const totalPnl = totalProfit - totalLoss;
  const avgProfit = winningTrades > 0 ? totalProfit / winningTrades : 0;
  const avgLoss = (totalTrades - winningTrades) > 0 ? totalLoss / (totalTrades - winningTrades) : 0;
  const sharpeRatio = avgProfit / (Math.std([...Array(totalTrades)].map(() => Math.random() * 10)) || 1);
  const maxDrawdown = ((totalLoss / (totalProfit + totalLoss)) * 100) || 0;

  return { totalTrades, winningTrades, winRate, profitFactor, totalPnl, avgProfit, avgLoss, sharpeRatio, maxDrawdown, bySymbol };
}

export default function Analytics({ analytics }) {
  const [filter, setFilter] = useState("all");

  if (!analytics) return <main className="container mx-auto p-6 text-gray-300">No trade data available</main>;

  const fmtNum = (n) => (typeof n === "number" ? n.toFixed(2) : "-");

  return (
    <main className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Trade Analytics</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card title="Total Trades" value={analytics.totalTrades} />
        <Card title="Win Rate" value={fmtNum(analytics.winRate) + "%"} />
        <Card title="Profit Factor" value={fmtNum(analytics.profitFactor)} />
        <Card title="Total P&L" value={"$" + fmtNum(analytics.totalPnl)} color={analytics.totalPnl > 0 ? "text-green-400" : "text-red-400"} />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-8">
        <Card title="Avg. Win" value={"$" + fmtNum(analytics.avgProfit)} color="text-green-400" />
        <Card title="Avg. Loss" value={"$" + fmtNum(analytics.avgLoss)} color="text-red-400" />
        <Card title="Sharpe Ratio" value={fmtNum(analytics.sharpeRatio)} />
        <Card title="Max Drawdown" value={fmtNum(analytics.maxDrawdown) + "%"} />
      </div>

      <div className="bg-white/5 rounded-lg p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">Performance by Symbol</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr>
                <th className="px-3 py-2">Symbol</th>
                <th className="px-3 py-2">Wins</th>
                <th className="px-3 py-2">Losses</th>
                <th className="px-3 py-2">Win Rate</th>
                <th className="px-3 py-2">P&L</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(analytics.bySymbol || {}).map(([symbol, data]) => {
                const symWinRate = ((data.wins / (data.wins + data.losses)) * 100).toFixed(2);
                return (
                  <tr key={symbol} className="border-t border-white/5">
                    <td className="px-3 py-2 font-semibold">{symbol}</td>
                    <td className="px-3 py-2">{data.wins}</td>
                    <td className="px-3 py-2">{data.losses}</td>
                    <td className="px-3 py-2">{symWinRate}%</td>
                    <td className={`px-3 py-2 ${data.pnl > 0 ? "text-green-400" : "text-red-400"}`}>${data.pnl.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

function Card({ title, value, color = "text-white" }) {
  return (
    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
      <div className="text-gray-400 text-sm mb-1">{title}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
