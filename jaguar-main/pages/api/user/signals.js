import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return res.status(401).json({ error: "not authenticated" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return res.status(500).json({ error: "Supabase admin client not configured" });
  }

  const limit = Math.min(Math.max(Number(req.query.limit) || 20, 1), 100);
  const { data, error } = await supabaseAdmin
    .from("signal_deliveries")
    .select(`
      id,
      plan,
      daily_limit,
      status,
      delivered_at,
      bot_signals:signal_id (
        id,
        symbol,
        direction,
        entry_price,
        stop_loss,
        take_profit,
        signal_quality,
        confidence,
        reason,
        created_at,
        status
      )
    `)
    .eq("user_id", session.user.id)
    .order("delivered_at", { ascending: false })
    .limit(limit);

  if (error?.code === "42P01" || error?.code === "42703") {
    return res.status(200).json({ signals: [], missingTable: true });
  }
  if (error) return res.status(500).json({ error: error.message || "Unable to load signals" });

  return res.status(200).json({
    signals: (data || []).map((delivery) => ({
      id: delivery.id,
      plan: delivery.plan,
      dailyLimit: delivery.daily_limit,
      deliveryStatus: delivery.status,
      deliveredAt: delivery.delivered_at,
      ...(delivery.bot_signals || {}),
    })),
  });
}
