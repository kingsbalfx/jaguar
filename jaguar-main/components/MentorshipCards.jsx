export default function MentorshipCards({ assignmentReview = false }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <div className="glass-panel rounded-2xl p-5">
        <h3 className="font-semibold">Learning Progress</h3>
        <p className="mt-2 text-sm text-gray-300">Follow the lesson sequence and complete each practical exercise.</p>
      </div>
      <div className="glass-panel rounded-2xl p-5">
        <h3 className="font-semibold">Trading Journal Coming Soon</h3>
        <p className="mt-2 text-sm text-gray-300">Prepare to document decisions, risk, outcomes, and lessons learned.</p>
      </div>
      {assignmentReview && (
        <div className="glass-panel rounded-2xl p-5">
          <h3 className="font-semibold">Assignment Review</h3>
          <p className="mt-2 text-sm text-gray-300">Submit structured work for mentor feedback and correction.</p>
        </div>
      )}
    </div>
  );
}
