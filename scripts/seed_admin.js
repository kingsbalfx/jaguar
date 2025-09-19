// scripts/seed_admin.js
import { createClient } from "@supabase/supabase-js";
import "dotenv/config";

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY,
);

const ADMIN_EMAIL = "shafiuabdullahi.sa3@gmail.com";
const ADMIN_PASSWORD = "014/Pt/014";

async function seedAdmin() {
  console.log("🔄 Checking if admin already exists...");

  const { data: existingUsers, error: checkError } = await supabase
    .from("profiles")
    .select("*")
    .eq("email", ADMIN_EMAIL);

  if (checkError) {
    console.error("❌ Error checking profiles:", checkError.message);
    process.exit(1);
  }

  if (existingUsers && existingUsers.length > 0) {
    console.log("⚠️ Admin already exists:", existingUsers[0].email);
    process.exit(0);
  }

  console.log("👤 Creating new admin...");

  const { data: user, error: userError } = await supabase.auth.admin.createUser({
    email: ADMIN_EMAIL,
    password: ADMIN_PASSWORD,
    email_confirm: true,
  });

  if (userError) {
    console.error("❌ Error creating admin user:", userError.message);
    process.exit(1);
  }

  const { error: profileError } = await supabase.from("profiles").insert([
    {
      id: user.user.id,
      email: ADMIN_EMAIL,
      role: "admin",
      name: "Kingsbal FX Admin",
      created_at: new Date().toISOString(),
    },
  ]);

  if (profileError) {
    console.error("❌ Error inserting profile:", profileError.message);
    process.exit(1);
  }

  console.log("✅ Admin seeded successfully:", ADMIN_EMAIL);
}

seedAdmin();
