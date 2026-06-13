export default function PlanInactivePanel({ planId }) {
  return (
    <div className="glass-panel rounded-2xl p-6 text-center">
      <h3 className="text-xl font-semibold">Plan inactive</h3>
      <p className="mt-2 text-gray-300">Your access is locked until your subscription is active again.</p>
      <a href={`/checkout?plan=${planId}`} className="mt-4 inline-flex rounded bg-indigo-600 px-4 py-2 text-white">
        Reactivate Plan
      </a>
    </div>
  );
}
