import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

function isMissingActiveColumn(error) {
  const msg = String(error?.message || "").toLowerCase();
  return (
    error?.code === "42703" ||
    msg.includes("mt5_credentials.active") ||
    (msg.includes("column") && msg.includes("active"))
  );
}

function isMissingUpdatedAtColumn(error) {
  const msg = String(error?.message || "").toLowerCase();
  return (
    error?.code === "42703" ||
    msg.includes("mt5_credentials.updated_at") ||
    (msg.includes("column") && msg.includes("updated_at"))
  );
}

function normalizeCredentialColumns(columns, hasUpdatedAtColumn) {
  if (hasUpdatedAtColumn) {
    return columns;
  }

  return columns
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part && part !== "updated_at")
    .join(", ");
}

async function queryLatestCredentialRow(
  supabaseAdmin,
  columns,
  hasActiveColumn,
  hasUpdatedAtColumn
) {
  let query = supabaseAdmin
    .from("mt5_credentials")
    .select(normalizeCredentialColumns(columns, hasUpdatedAtColumn));

  if (hasActiveColumn) {
    query = query.eq("active", true);
  }

  if (hasUpdatedAtColumn) {
    query = query.order("updated_at", { ascending: false });
  }

  return query.limit(1).maybeSingle();
}

async function getLatestCredentialRow(
  supabaseAdmin,
  columns = "login, server, updated_at"
) {
  let hasActiveColumn = true;
  let hasUpdatedAtColumn = true;

  for (let attempt = 0; attempt < 4; attempt += 1) {
    const result = await queryLatestCredentialRow(
      supabaseAdmin,
      columns,
      hasActiveColumn,
      hasUpdatedAtColumn
    );

    if (!result.error) {
      return {
        row: result.data || null,
        hasActiveColumn,
        hasUpdatedAtColumn,
        error: null,
      };
    }

    if (hasActiveColumn && isMissingActiveColumn(result.error)) {
      hasActiveColumn = false;
      continue;
    }

    if (hasUpdatedAtColumn && isMissingUpdatedAtColumn(result.error)) {
      hasUpdatedAtColumn = false;
      continue;
    }

    return {
      row: null,
      hasActiveColumn,
      hasUpdatedAtColumn,
      error: result.error,
    };
  }

  return {
    row: null,
    hasActiveColumn,
    hasUpdatedAtColumn,
    error: new Error("failed to resolve mt5_credentials schema"),
  };
}

async function deactivateCurrentCredentials(supabaseAdmin, hasActiveColumn) {
  if (!hasActiveColumn) return null;

  const { error } = await supabaseAdmin
    .from("mt5_credentials")
    .update({ active: false })
    .eq("active", true);

  if (error && isMissingActiveColumn(error)) {
    return null;
  }

  return error || null;
}

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).end();
  }

  try {
    const supabase = createPagesServerClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) {
      return res.status(401).json({ error: "not authenticated" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) {
      return res
        .status(500)
        .json({ error: "Supabase admin client not configured" });
    }

    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") {
      return res.status(403).json({ error: "forbidden" });
    }

    if (req.method === "GET") {
      const { row, error } = await getLatestCredentialRow(
        supabaseAdmin,
        "login, server, updated_at"
      );

      if (error) {
        return res.status(500).json({ error: "failed to load credentials" });
      }

      return res.status(200).json({
        credentials: row
          ? {
              login: row.login || "",
              server: row.server || "",
              updated_at: row.updated_at || null,
              hasPassword: true,
            }
          : {
              login: "",
              server: "",
              updated_at: null,
              hasPassword: false,
            },
      });
    }

    const { login, password, server } = req.body || {};
    const cleanLogin = String(login || "").trim();
    const cleanServer = String(server || "").trim();
    const cleanPassword = String(password || "");

    if (!cleanLogin || !cleanServer) {
      return res
        .status(400)
        .json({ error: "login and server are required" });
    }

    const {
      row: currentActive,
      error: currentError,
      hasActiveColumn,
      hasUpdatedAtColumn,
    } = await getLatestCredentialRow(supabaseAdmin, "password, updated_at");

    if (currentError) {
      return res.status(500).json({
        error: currentError.message || "failed to load current credentials",
      });
    }

    const passwordToSave = cleanPassword || currentActive?.password || "";
    if (!passwordToSave) {
      return res.status(400).json({
        error: "password is required for first-time setup",
      });
    }

    const deactivateError = await deactivateCurrentCredentials(
      supabaseAdmin,
      hasActiveColumn
    );

    if (deactivateError) {
      return res.status(500).json({
        error: deactivateError.message || "failed to rotate credentials",
      });
    }

    const payload = {
      login: cleanLogin,
      password: passwordToSave,
      server: cleanServer,
    };

    if (hasActiveColumn) {
      payload.active = true;
    }

    if (hasUpdatedAtColumn) {
      payload.updated_at = new Date().toISOString();
    }

    const { error: insertError } = await supabaseAdmin
      .from("mt5_credentials")
      .insert(payload);

    if (insertError) {
      return res.status(500).json({
        error: insertError.message || "failed to save credentials",
      });
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
