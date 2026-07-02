export const SIGNAL_GATE_KEY = "bot_signal_gate";

export const DEFAULT_SIGNAL_GATE = {
  paused: false,
  resume_at: null,
  message: "",
  updated_at: null,
};

export function defaultSignalPauseMessage(resumeAt) {
  const dateLabel = formatResumeDate(resumeAt);
  return `Bot signal delivery is temporarily paused${dateLabel ? ` until ${dateLabel}` : ""}. No signal emails or dashboard alerts will be sent while this pause is active.`;
}

export function formatResumeDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  });
}

export function normalizeSignalGate(record) {
  const settings = record?.settings && typeof record.settings === "object" ? record.settings : {};
  const resumeAt = settings.resume_at || record?.resume_at || null;
  const paused = Boolean(settings.paused);
  const message = String(settings.message || "").trim() || defaultSignalPauseMessage(resumeAt);
  return {
    paused,
    resume_at: resumeAt,
    message,
    updated_at: record?.updated_at || settings.updated_at || null,
  };
}

export function isSignalGateActive(gate = DEFAULT_SIGNAL_GATE) {
  if (!gate.paused) return false;
  if (!gate.resume_at) return true;
  const resumeTime = new Date(gate.resume_at).getTime();
  if (Number.isNaN(resumeTime)) return true;
  return Date.now() < resumeTime;
}

export async function getSignalGate(supabaseAdmin) {
  if (!supabaseAdmin) return { gate: DEFAULT_SIGNAL_GATE, active: false, missingTable: false };
  const { data, error } = await supabaseAdmin
    .from("site_settings")
    .select("key,settings,updated_at")
    .eq("key", SIGNAL_GATE_KEY)
    .maybeSingle();

  if (error) {
    const msg = String(error.message || "").toLowerCase();
    const missingTable = error.code === "42P01" || msg.includes("does not exist") || msg.includes("schema cache");
    if (missingTable) return { gate: DEFAULT_SIGNAL_GATE, active: false, missingTable: true };
    throw error;
  }

  const gate = data ? normalizeSignalGate(data) : DEFAULT_SIGNAL_GATE;
  return { gate, active: isSignalGateActive(gate), missingTable: false };
}

export async function saveSignalGate(supabaseAdmin, gate) {
  const payload = {
    key: SIGNAL_GATE_KEY,
    settings: {
      paused: Boolean(gate.paused),
      resume_at: gate.resume_at || null,
      message: String(gate.message || "").trim() || defaultSignalPauseMessage(gate.resume_at),
      updated_at: new Date().toISOString(),
    },
    updated_at: new Date().toISOString(),
  };

  const { data, error } = await supabaseAdmin
    .from("site_settings")
    .upsert(payload, { onConflict: "key" })
    .select("key,settings,updated_at")
    .maybeSingle();

  if (error) throw error;
  return normalizeSignalGate(data);
}

export async function assertSignalDeliveryOpen(supabaseAdmin) {
  const { gate, active } = await getSignalGate(supabaseAdmin);
  if (active) {
    const error = new Error(gate.message || defaultSignalPauseMessage(gate.resume_at));
    error.code = "SIGNAL_DELIVERY_PAUSED";
    error.gate = gate;
    throw error;
  }
  return gate;
}
