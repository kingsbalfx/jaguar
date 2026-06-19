export const REGISTRATION_GATE_KEY = "registration_gate";

export const DEFAULT_REGISTRATION_GATE = {
  paused: false,
  reopen_at: null,
  message: "",
  updated_at: null,
};

export function defaultClosureMessage(reopenAt) {
  const dateLabel = formatReopenDate(reopenAt);
  return `Application has been closed. A class is already going on. Please wait until ${dateLabel || "the reopening date"} to apply for paid access. Free tier registration is still open.`;
}

export function formatReopenDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-NG", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Africa/Lagos",
  });
}

export function normalizeGateRecord(record) {
  const settings = record?.settings && typeof record.settings === "object" ? record.settings : {};
  const reopenAt = settings.reopen_at || record?.reopen_at || null;
  const paused = Boolean(settings.paused);
  const message = String(settings.message || "").trim() || defaultClosureMessage(reopenAt);
  return {
    paused,
    reopen_at: reopenAt,
    message,
    updated_at: record?.updated_at || settings.updated_at || null,
  };
}

export function isRegistrationGateActive(gate = DEFAULT_REGISTRATION_GATE) {
  if (!gate.paused) return false;
  if (!gate.reopen_at) return true;
  const reopenTime = new Date(gate.reopen_at).getTime();
  if (Number.isNaN(reopenTime)) return true;
  return Date.now() < reopenTime;
}

export async function getRegistrationGate(supabaseAdmin) {
  if (!supabaseAdmin) return { gate: DEFAULT_REGISTRATION_GATE, missingTable: false };
  const { data, error } = await supabaseAdmin
    .from("site_settings")
    .select("key,settings,updated_at")
    .eq("key", REGISTRATION_GATE_KEY)
    .maybeSingle();

  if (error) {
    const msg = String(error.message || "").toLowerCase();
    const missingTable = error.code === "42P01" || msg.includes("does not exist") || msg.includes("schema cache");
    if (missingTable) return { gate: DEFAULT_REGISTRATION_GATE, missingTable: true };
    throw error;
  }

  return { gate: data ? normalizeGateRecord(data) : DEFAULT_REGISTRATION_GATE, missingTable: false };
}

export async function saveRegistrationGate(supabaseAdmin, gate) {
  const payload = {
    key: REGISTRATION_GATE_KEY,
    settings: {
      paused: Boolean(gate.paused),
      reopen_at: gate.reopen_at || null,
      message: String(gate.message || "").trim(),
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
  return normalizeGateRecord(data);
}
