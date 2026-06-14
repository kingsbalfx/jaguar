export const MENTORSHIP_GROUPS = [
  { value: "all", label: "Everyone", description: "Publish to every signed-in learner.", accent: "from-emerald-500/25 to-cyan-500/10" },
  { value: "free", label: "Starter Resources", description: "Free lessons and introductory resources.", accent: "from-amber-500/25 to-orange-500/10" },
  { value: "premium", label: "Academy Students", description: "Structured academy lessons and weekly classes.", accent: "from-blue-500/25 to-indigo-500/10" },
  { value: "vip", label: "Review & Mentorship", description: "Assignment review, journals, and priority Q&A.", accent: "from-purple-500/25 to-fuchsia-500/10" },
  { value: "pro", label: "Private Coaching", description: "Advanced strategy correction and private mentorship.", accent: "from-indigo-500/25 to-violet-500/10" },
  { value: "lifetime", label: "Lifetime Library", description: "Permanent course vault and future updates.", accent: "from-pink-500/25 to-rose-500/10" },
];

export function getMentorshipGroup(value) {
  return MENTORSHIP_GROUPS.find((group) => group.value === String(value || "").toLowerCase()) || MENTORSHIP_GROUPS[0];
}

export function getMentorshipGroupLabel(value) {
  return getMentorshipGroup(value).label;
}
