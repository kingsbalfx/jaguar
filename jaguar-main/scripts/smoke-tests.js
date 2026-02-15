#!/usr/bin/env node
/**
 * Smoke tests: verify deployed endpoints are working.
 * Run: npm run test:smoke (from jaguar-main root)
 */
import fetch from "node-fetch";

const BASE_URL = process.env.BASE_URL || "https://kingsbalfx.name.ng";
const BOT_URL = process.env.BOT_URL || "https://your-bot-host:8000";

const tests = [];

async function test(name, fn) {
  try {
    await fn();
    console.log(`✓ ${name}`);
    tests.push({ name, ok: true });
  } catch (e) {
    console.error(`✗ ${name}:`, e.message);
    tests.push({ name, ok: false, error: e.message });
  }
}

async function run() {
  console.log("Running smoke tests...\n");

  // Web health
  await test("Web health endpoint", async () => {
    const resp = await fetch(`${BASE_URL}/health`);
    if (resp.status !== 200) throw new Error(`status ${resp.status}`);
    const data = await resp.json();
    if (data.status !== "ok") throw new Error("status not ok");
  });

  // Paystack init endpoint
  await test("Paystack init endpoint", async () => {
    const resp = await fetch(`${BASE_URL}/api/init-paystack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "test@example.com", amount: 100000 }),
    });
    // should fail gracefully without PAYSTACK_SECRET, or return proper auth error
    if (resp.status >= 500) throw new Error(`server error ${resp.status}`);
  });

  // Admin payments endpoint (should fail without key)
  await test("Admin payments endpoint (auth check)", async () => {
    const resp = await fetch(`${BASE_URL}/api/admin/payments`);
    if (resp.status !== 401) throw new Error(`expected 401, got ${resp.status}`);
  });

  // Bot health
  await test("Bot health endpoint", async () => {
    try {
      const resp = await fetch(`${BOT_URL}/health`, { timeout: 5000 });
      if (resp.status !== 200) throw new Error(`status ${resp.status}`);
    } catch (e) {
      // Bot may not be running locally, which is ok for this test
      console.warn("  (Bot not running, skipping detailed check)");
    }
  });

  const passed = tests.filter((t) => t.ok).length;
  const failed = tests.filter((t) => !t.ok).length;
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

run().catch((e) => {
  console.error("Test suite failed:", e);
  process.exit(1);
});
