import { createClient } from "@supabase/supabase-js";
import "dotenv/config";

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
);

(async () => {
  try {
    console.log("🔎 Testing Supabase connection...");

    const { data, error } = await supabase.from("profiles").select("count");
    if (error) {
      console.error("❌ Query error:", error.message);
    } else {
      console.log("✅ Connected! Profiles table count:", data);
    }
  } catch (err) {
    console.error("❌ Fetch failed:", err);
  }
})();
