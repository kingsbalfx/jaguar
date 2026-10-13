// scripts/check-mt5-bridge.js
/**
 * MT5 bridge diagnostics. Answers three questions without leaking secrets:
 *   1. which provider is active, and what is still missing?
 *   2. is the sync plumbing (encryption secret, cron secret, Supabase) present?
 *   3. does the bridge actually answer?  (--probe / --deals)
 *
 * Usage:
 *   node scripts/check-mt5-bridge.js
 *   node scripts/check-mt5-bridge.js --probe
 *   node scripts/check-mt5-bridge.js --deals --login=5551234 --server=Broker-Demo --days=3
 *   node scripts/check-mt5-bridge.js --deals --login=5551234 --accountId=<metaapi id>
 *
 * Loads .env.local then .env (same precedence as Next.js). Values are never printed.
 */
import fs from "fs";
import dotenv from "dotenv";

for (const file of [".env.local", ".env"]) {
  if (fs.existsSync(file)) dotenv.config({ path: file });
}

const { getBridgeHealth, metaApiConfig, relayConfig, webApiConfig, requestJson, fetchDealsForLink } = await import(
  "../lib/mt5-bridge.js"
);

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const option = (name, fallback = "") => {
  const hit = args.find((arg) => arg.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3).trim() : fallback;
};
const mark = (ok) => (ok ? "OK  " : "MISS");

const health = getBridgeHealth();

console.log("\nMT5 bridge diagnostics");
console.log("======================");
console.log(`active provider : ${health.provider || "(none)"}${health.forced ? "  (forced by MT5_BRIDGE_PROVIDER)" : "  (auto-detected)"}`);
console.log(`configured      : ${health.configured ? "yes" : "no"}`);
if (health.reason) console.log(`reason          : ${health.reason}`);
console.log(`request timeout : ${health.requestTimeoutMs} ms  (MT5_BRIDGE_TIMEOUT_MS)`);

console.log("\nproviders (first configured one wins when MT5_BRIDGE_PROVIDER is unset)");
for (const provider of health.providers) {
  console.log(`  ${mark(provider.configured)} ${String(provider.provider).padEnd(10)} ${provider.reason || "ready"}`);
}

console.log("\nresolved endpoints (secrets hidden)");
console.log(`  metaapi    client       ${health.metaApi.clientBase}`);
console.log(`             region       ${health.metaApi.region || "(default host)"}   token: ${health.metaApi.tokenPresent ? "present" : "absent"}`);
console.log(`  relay      base         ${health.relay.baseUrl || "(unset)"}`);
console.log(`             path         ${health.relay.path}   token: ${health.relay.tokenPresent ? "present" : "absent"}`);
console.log(`  mt5webapi  base         ${health.webApi.baseUrl || "(unset)"}`);
console.log(`             manager      ${health.webApi.login || "(unset)"}   password: ${health.webApi.passwordPresent ? "present" : "absent"}`);

console.log("\nsync plumbing (needed for every provider)");
for (const [name, why] of [
  ["MT5_CREDENTIALS_SECRET", "encrypts MT5 passwords in mt5_account_links (AES-256-GCM)"],
  ["CRON_SECRET", "authorises /api/cron/mt5-sync"],
  ["NEXT_PUBLIC_SUPABASE_URL", "Supabase project URL"],
  ["SUPABASE_SERVICE_ROLE_KEY", "server-side table access"],
]) {
  console.log(`  ${mark(Boolean(process.env[name]))} ${name.padEnd(26)} ${why}`);
}

let problems = health.configured ? 0 : 1;

if (!health.configured) {
  console.log("\nNothing is configured yet. Set ONE provider in .env.local (and in Vercel):");
  console.log("  METAAPI_TOKEN=...                                    # hosted MetaApi terminal (recommended)");
  console.log("  BOT_API_URL=... BOT_API_TOKEN=...                    # relay on the bot host");
  console.log("  MT5_WEBAPI_URL=... MT5_WEBAPI_LOGIN=... MT5_WEBAPI_PASSWORD=...   # broker WebAPI");
}

/** MetaApi: list the provisioned cloud terminals (the auth-token is the only secret needed). */
async function probeMetaApi() {
  const { token, provisioningBase } = metaApiConfig();
  const payload = await requestJson(`${provisioningBase}/users/current/accounts`, { headers: { "auth-token": token } });
  const list = Array.isArray(payload) ? payload : payload?.items || [];
  const sample = list.slice(0, 5).map((account) => account?.login || account?._id).join(", ");
  return `${list.length} provisioned account(s)${sample ? `: ${sample}` : " (none yet - they are created when a user links an account)"}`;
}

/** Relay: the bot host exposes /health, so reachability can be checked without an account. */
async function probeRelay() {
  const { baseUrl } = relayConfig();
  const payload = await requestJson(`${baseUrl}/health`);
  const text = typeof payload === "string" ? payload : JSON.stringify(payload);
  return `bot host /health responded: ${text.slice(0, 160)}`;
}

/** WebAPI: reproduce the manager auth/start handshake (retcode 0 = credentials accepted). */
async function probeWebApi() {
  const { baseUrl, login } = webApiConfig();
  const payload = await requestJson(`${baseUrl}/api/auth/start`, {
    method: "POST",
    body: { version: "3.16", agent: "kingsbalfx-sync", login: String(login), type: "manager" },
  });
  const retcode = payload?.retcode ?? payload?.answer?.retcode ?? payload?.RetCode;
  return `auth/start answered${retcode === undefined ? "" : ` (retcode ${retcode})`}`;
}

const PROBES = { metaapi: probeMetaApi, relay: probeRelay, mt5webapi: probeWebApi };

if (flag("probe") || flag("deals")) {
  console.log("\nlive probes");
  if (!health.provider) {
    console.log("  skipped: no provider is configured");
  } else {
    try {
      console.log(`  ${health.provider}: ${await PROBES[health.provider]()}`);
    } catch (error) {
      problems += 1;
      console.log(`  ${health.provider}: FAILED - ${error?.message || error}`);
    }
  }
}

if (flag("deals")) {
  const login = option("login");
  const server = option("server");
  const accountId = option("accountId");
  const days = Math.max(1, Math.min(Number(option("days", "3")) || 3, 365));
  if (!login) {
    problems += 1;
    console.log("  deals: needs --login=<mt5 login> [--server=<server>] (plus --accountId for MetaApi)");
  } else {
    const until = new Date();
    const since = new Date(until.getTime() - days * 24 * 60 * 60 * 1000);
    try {
      const result = await fetchDealsForLink({
        link: { login, server, provider: health.provider, bridge_account_id: accountId },
        since,
        until,
      });
      console.log(
        `  deals: ${result.deals.length} deal(s) from ${result.provider} between ${since.toISOString()} and ${until.toISOString()}`,
      );
      for (const deal of result.deals.slice(0, 3)) {
        console.log(`         ${JSON.stringify(deal).slice(0, 180)}`);
      }
      if (!result.deals.length) console.log("         (an empty window is normal for a quiet account)");
    } catch (error) {
      problems += 1;
      console.log(`  deals: FAILED - ${error?.message || error}`);
    }
  }
}

console.log(
  problems
    ? "\nResult: action needed (see the messages above). Run `npm run verify:mt5-sync` for the offline suite.\n"
    : "\nResult: bridge looks healthy.\n",
);
process.exitCode = problems ? 1 : 0;

