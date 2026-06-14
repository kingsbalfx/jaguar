import { useEffect, useState } from "react";
import FeedbackMessage from "./FeedbackMessage";

function ResultTable({ title, rows, competition = false }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/10 bg-black/20 p-4">
      <h3 className="font-semibold text-white">{title}</h3>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="text-xs uppercase text-gray-400">
            <tr>
              <th className="px-2 py-2">Student</th>
              <th className="px-2 py-2">{competition ? "Competition" : "Quiz"}</th>
              <th className="px-2 py-2">{competition ? "Points" : "Score"}</th>
              <th className="px-2 py-2">{competition ? "Rank" : "Completed"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-white/10 text-gray-200">
                <td className="px-2 py-3">{row.email || "Student"}</td>
                <td className="px-2 py-3">{competition ? row.competition_title : row.quiz_title}</td>
                <td className="px-2 py-3">{competition ? row.points : `${row.score}/${row.total}`}</td>
                <td className="px-2 py-3">{competition ? row.rank || "-" : new Date(row.completed_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="py-5 text-sm text-gray-400">No results recorded for this group yet.</div>}
      </div>
    </div>
  );
}

export default function PlanPerformancePanel({ plan }) {
  const [data, setData] = useState({ quizzes: [], competitions: [] });
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`/api/group-performance?plan=${encodeURIComponent(plan)}`)
      .then(async (response) => {
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Unable to load group performance.");
        setData(result);
      })
      .catch((err) => setError(err.message));
  }, [plan]);

  return (
    <section className="mt-6 glass-panel rounded-2xl p-4 sm:p-5">
      <div className="text-xs uppercase tracking-widest text-amber-200">{plan} group performance</div>
      <h2 className="mt-1 text-xl font-semibold">Quizzes & Competitions</h2>
      <p className="mt-1 text-sm text-gray-300">Results and rankings are visible only to members of this plan group.</p>
      <FeedbackMessage message={error} type="error" />
      {data.setupRequired && <div className="mt-3 text-sm text-amber-200">Run the group performance SQL migration to begin recording results.</div>}
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <ResultTable title="Quiz Results" rows={data.quizzes || []} />
        <ResultTable title="Competition Leaderboard" rows={data.competitions || []} competition />
      </div>
    </section>
  );
}
