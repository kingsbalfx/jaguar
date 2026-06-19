import { getSupabaseClient } from "../../lib/supabaseClient";
import { getRegistrationGate, isRegistrationGateActive } from "../../lib/registration-gate";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  try {
    const supabaseAdmin = getSupabaseClient({ server: true });
    const { gate, missingTable } = await getRegistrationGate(supabaseAdmin);
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({
      gate,
      active: isRegistrationGateActive(gate),
      missingTable,
    });
  } catch (err) {
    console.error("registration-gate public error:", err);
    return res.status(200).json({
      gate: { paused: false, reopen_at: null, message: "", updated_at: null },
      active: false,
      error: "registration gate unavailable",
    });
  }
}
