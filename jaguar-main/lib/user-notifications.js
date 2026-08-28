export async function findUserIdByEmail(supabaseAdmin, email) {
  if (!supabaseAdmin || !email) return null;
  const normalizedEmail = String(email).trim().toLowerCase();
  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("id")
    .ilike("email", normalizedEmail)
    .maybeSingle();
  if (profile?.id) return profile.id;

  try {
    const { data: authData } = await supabaseAdmin.auth.admin.listUsers({ page: 1, perPage: 1000 });
    const authUser = (authData?.users || []).find(
      (user) => String(user.email || "").trim().toLowerCase() === normalizedEmail
    );
    return authUser?.id || null;
  } catch (error) {
    console.warn("notification auth lookup failed:", error?.message || error);
    return null;
  }
}

export async function createUserNotification({ supabaseAdmin, userId, email, title, body, link, type, dedupeKey }) {
  if (!supabaseAdmin) return { notified: false, reason: "missing_supabase" };
  const targetUserId = userId || await findUserIdByEmail(supabaseAdmin, email);
  if (!targetUserId) return { notified: false, reason: "missing_user" };

  const insert = await supabaseAdmin.from("user_notifications").insert({
    user_id: targetUserId,
    title,
    body,
    link: link || null,
    notification_type: type || "general",
    dedupe_key: dedupeKey || null,
    read_at: null,
    created_at: new Date().toISOString(),
  });

  if (insert.error && insert.error.code !== "23505") {
    console.warn("user notification failed:", insert.error.message);
    return { notified: false, reason: insert.error.message };
  }
  return { notified: true };
}
