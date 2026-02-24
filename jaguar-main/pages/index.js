// pages/index.js
import React, { useState } from "react";
import Link from "next/link";
import AdSense from "../components/AdSense";
import { getSupabaseClient } from "../lib/supabaseClient";
import dynamic from "next/dynamic";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";

const TwilioVideoClient = dynamic(() => import("../components/TwilioVideoClient"), { ssr: false });

const ROLE_RANK = {
  free: 0,
  user: 0,
  premium: 1,
  vip: 2,
  pro: 3,
  lifetime: 4,
  admin: 99,
  all: 0,
};

function canAccess(role, segment) {
  const r = ROLE_RANK[role] ?? 0;
  const s = ROLE_RANK[segment] ?? 0;
  return r >= s;
}

function toYouTubeEmbed(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtu.be")) {
      const id = parsed.pathname.replace("/", "");
      return `https://www.youtube.com/embed/${id}`;
    }
    if (parsed.searchParams.get("v")) {
      return `https://www.youtube.com/embed/${parsed.searchParams.get("v")}`;
    }
    return url;
  } catch {
    return url;
  }
}

async function fetchMessagesWithFallback(client) {
  let { data, error } = await client
    .from("messages")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);

  if (error && error.code === "42703") {
    ({ data, error } = await client
      .from("messages")
      .select("*")
      .order("id", { ascending: false })
      .limit(20));
  }

  return { data, error };
}

export async function getServerSideProps(ctx) {
  const authClient = createPagesServerClient(ctx);
  const {
    data: { session },
  } = await authClient.auth.getSession();
  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return { props: { initialMessages: [], liveSession: null, canViewLive: false } };
  }

  try {
    const { data, error } = await fetchMessagesWithFallback(supabaseAdmin);
    if (error) {
      console.error("Landing messages error:", error);
      return { props: { initialMessages: [], liveSession: null, canViewLive: false } };
    }

    let liveSession = null;
    try {
      const { data: sessionData, error: sessionErr } = await supabaseAdmin
        .from("live_sessions")
        .select("*")
        .eq("active", true)
        .order("starts_at", { ascending: true })
        .limit(1)
        .maybeSingle();
      if (!sessionErr) liveSession = sessionData || null;
      if (sessionErr && sessionErr.code !== "42P01") {
        console.error("Live session fetch error:", sessionErr);
      }
    } catch (err) {
      console.error("Live session fetch error:", err);
    }

    let viewerRole = "user";
    if (session?.user) {
      const { data: profile } = await supabaseAdmin
        .from("profiles")
        .select("role")
        .eq("id", session.user.id)
        .maybeSingle();
      viewerRole = (profile?.role || "user").toLowerCase();
    }
    const subscriberRoles = new Set(["premium", "vip", "pro", "lifetime", "admin"]);
    const canViewLive =
      Boolean(session?.user) &&
      subscriberRoles.has(viewerRole) &&
      (liveSession ? canAccess(viewerRole, liveSession.segment || "all") : false);

    return { props: { initialMessages: data || [], liveSession, canViewLive } };
  } catch (err) {
    console.error("Landing messages error:", err);
    return { props: { initialMessages: [], liveSession: null, canViewLive: false } };
  }
}

export default function Home({ initialMessages = [], liveSession = null, canViewLive = false }) {
  const [mode, setMode] = useState("free"); // free | premium | vip | pro | lifetime
  const defaultMessages = [
    { id: 1, text: "Precision entries. Disciplined exits. Every signal measured.", segments: ["all"] },
    { id: 2, text: "VIP weekly signals are live with full trade walkthroughs.", segments: ["vip"] },
    { id: 3, text: "New lesson drop: Market Structure & Liquidity Sweeps.", segments: ["premium", "vip"] },
    { id: 4, text: "Premium & VIP challenge starts this week - join the desk.", segments: ["premium", "vip"] },
    { id: 5, text: "VIP 1:1 mentorship slots open for serious traders.", segments: ["vip"] },
    { id: 6, text: "Pro tier unlocks 1:1 coaching, custom strategies, and advanced analytics.", segments: ["pro"] },
    { id: 7, text: "Lifetime members get permanent access to every update, session, and signal.", segments: ["lifetime"] },
    { id: 8, text: "Pro & Lifetime tiers include priority execution and concierge support.", segments: ["pro", "lifetime"] },
  ];
  const normalizedMessages = (initialMessages.length ? initialMessages : defaultMessages).map((m, i) => {
    const segments = Array.isArray(m.segments)
      ? m.segments
      : m.segment
        ? [m.segment]
        : ["all"];
    return {
      id: m.id ?? i + 1,
      text: m.content ?? m.text ?? m.message ?? "",
      segments,
    };
  });

  const toggleDescriptions = {
    free: "Free trial access to starter signals and weekly lesson drops.",
    premium: "Premium adds daily signals, bot access, and advanced analytics.",
    vip: "VIP unlocks mentorship sessions, priority support, and deeper trade guidance.",
    pro: "Pro gives 1:1 coaching, custom strategies, and elite execution rules.",
    lifetime: "Lifetime members keep every upgrade, session, and signal forever.",
  };

  const toggleStyles = {
    free: { color: "#fbbf24", border: "rgba(251, 191, 36, 0.6)", label: "Free Trial" },
    premium: { color: "#3b82f6", border: "rgba(59, 130, 246, 0.6)", label: "Premium" },
    vip: { color: "#a855f7", border: "rgba(168, 85, 247, 0.6)", label: "VIP" },
    pro: { color: "#6366f1", border: "rgba(99, 102, 241, 0.6)", label: "Pro" },
    lifetime: { color: "#ec4899", border: "rgba(236, 72, 153, 0.6)", label: "Lifetime" },
  };

  const visibleMessages = normalizedMessages.filter(
    (m) => m.segments.includes("all") || m.segments.includes(mode)
  );
  return (
    <main className="flex-grow app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-6 py-14">
        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-1 text-xs uppercase tracking-widest text-indigo-200">
              KingsBalfx Trading Lab
            </div>
            <h1 className="display-font mt-4 text-4xl md:text-6xl font-bold leading-tight">
              Forex mentorship, live signals, and a bot engine built for consistency.
            </h1>
            <p className="mt-4 text-lg text-gray-300 max-w-2xl">
              Build your edge with guided ICT strategy, disciplined risk controls, and signals tuned
              to your tier. Every plan delivers actionable setups, clean execution, and a clear
              growth path.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/pricing">
                <a className="px-6 py-3 rounded-lg text-white font-semibold btn-primary">
                  View Pricing
                </a>
              </Link>
              <Link href="/register">
                <a className="px-6 py-3 rounded-lg text-white/90 btn-outline">
                  Start Free Trial
                </a>
              </Link>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Signals / Day</div>
                <div className="mt-2 text-lg font-semibold">Up to 30+</div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Bot Risk Caps</div>
                <div className="mt-2 text-lg font-semibold">Tier‑Based</div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Mentorship</div>
                <div className="mt-2 text-lg font-semibold">Weekly Live</div>
              </div>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-6 relative overflow-hidden">
            <div className="absolute -top-20 -right-24 h-48 w-48 rounded-full bg-indigo-500/20 blur-3xl" />
            <div className="absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-yellow-400/10 blur-3xl" />
            <div className="relative space-y-4">
              <div className="text-sm text-indigo-200">Live Bot Snapshot</div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Signal Quality</div>
                <div className="mt-1 text-xl font-semibold">Premium Confidence</div>
                <p className="mt-2 text-sm text-gray-300">
                  Filters tuned to liquidity sweeps, structure shifts, and HTF momentum.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Execution Layer</div>
                <div className="mt-1 text-xl font-semibold">Risk‑Locked Entries</div>
                <p className="mt-2 text-sm text-gray-300">
                  Dynamic lot sizing with max‑trade guards and tiered exposure rules.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Community</div>
                <div className="mt-1 text-xl font-semibold">Mentor‑Led Rooms</div>
                <p className="mt-2 text-sm text-gray-300">
                  Daily breakdowns, session recaps, and accountability check‑ins.
                </p>
              </div>
            </div>
          </div>
        </div>

        <section className="mt-12">
          {liveSession && (
            <div className="mb-6 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-4">
              <div className="text-xs uppercase tracking-widest text-emerald-200 mb-2">
                Live Session
              </div>
              <div className="text-lg font-semibold text-white">
                {liveSession.title || "Next Live Session"}
              </div>
              <div className="mt-1 text-sm text-emerald-100/80">
                {liveSession.starts_at
                  ? new Date(liveSession.starts_at).toLocaleString()
                  : "Time not set"}
                {liveSession.ends_at ? ` — ${new Date(liveSession.ends_at).toLocaleTimeString()}` : ""}
                {liveSession.timezone ? ` (${liveSession.timezone})` : ""}
              </div>
              {canViewLive ? (
                <div className="mt-4">
                  {liveSession.media_type === "youtube" && liveSession.media_url && (
                    <div className="aspect-video w-full overflow-hidden rounded-lg border border-white/10">
                      <iframe
                        title="YouTube Live"
                        src={toYouTubeEmbed(liveSession.media_url)}
                        className="w-full h-full"
                        allow="autoplay; encrypted-media"
                        allowFullScreen
                      />
                    </div>
                  )}
                  {(liveSession.media_type === "twilio_video" ||
                    liveSession.media_type === "twilio_audio" ||
                    liveSession.media_type === "twilio_screen") && (
                    <div className="mt-3">
                      <TwilioVideoClient
                        roomName={liveSession.room_name || "global-room"}
                        audioOnly={Boolean(liveSession.audio_only)}
                        joinAudio={false}
                        joinVideo={false}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-4 text-sm text-emerald-100/70">
                  Live sessions are available to active subscribers.
                </div>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-3 mb-3">
            {Object.keys(toggleStyles).map((key) => {
              const style = toggleStyles[key];
              const isActive = mode === key;
              return (
                <button
                  key={key}
                  onClick={() => setMode(key)}
                  className={`fire-toggle ${isActive ? "is-active" : ""}`}
                  style={{
                    "--fire-color": style.color,
                    "--fire-border": style.border,
                  }}
                >
                  <span className={`fire-dot ${isActive ? "is-active" : ""}`} />
                  <span className="toggle-label">{style.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-sm text-gray-300 mb-6 max-w-3xl">
            {toggleDescriptions[mode]}
          </p>

          <div className="grid gap-4 md:grid-cols-2">
            {visibleMessages.map((m) => (
              <div key={m.id} className="glass-panel rounded-2xl p-4">
                {m.text}
              </div>
            ))}
          </div>

          {mode === "free" && (
            <div className="mt-8 rounded-2xl border border-yellow-400/30 bg-yellow-500/5 p-4">
              <div className="text-xs uppercase tracking-widest text-yellow-300 mb-2">
                Sponsored
              </div>
              <AdSense slot="1636184407" />
            </div>
          )}
        </section>

        <section className="mt-12 relative overflow-hidden rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-slate-950 via-indigo-950/60 to-black p-8">
          <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-yellow-400/10 blur-3xl" />

          <div className="relative grid gap-8 md:grid-cols-[1.1fr_0.9fr] items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-yellow-400/40 bg-yellow-400/10 px-3 py-1 text-xs uppercase tracking-widest text-yellow-300">
                Bot Trading Engine
              </div>
              <h2 className="mt-4 text-3xl md:text-4xl font-bold leading-tight">
                Automated entries, disciplined risk, and live signal delivery.
              </h2>
              <p className="mt-4 text-gray-300">
                Our bot blends ICT structure with tiered signal quality, protecting your capital while
                hunting high‑probability setups. Premium and VIP unlock stronger filters, higher
                trade limits, and priority execution logic.
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Signal Quality</div>
                  <div className="mt-1 text-lg font-semibold text-white">Tiered AI Scoring</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Trade Limits</div>
                  <div className="mt-1 text-lg font-semibold text-white">Smart Risk Caps</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Execution</div>
                  <div className="mt-1 text-lg font-semibold text-white">Real‑time Alerts</div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/pricing">
                  <a className="px-5 py-3 rounded-lg text-white font-semibold btn-primary">
                    Explore Bot Plans
                  </a>
                </Link>
                <Link href="/register">
                  <a className="px-5 py-3 rounded-lg text-yellow-200 border border-yellow-400/60 hover:bg-yellow-400/10 transition">
                    Start Free Trial
                  </a>
                </Link>
              </div>
            </div>

            <div className="grid gap-4">
              <div className="rounded-2xl border border-indigo-500/20 bg-black/40 p-6">
                <div className="text-sm text-indigo-200">What you get</div>
                <ul className="mt-4 space-y-2 text-sm text-gray-300">
                  <li>Live bot signals with clear SL/TP targets</li>
                  <li>Risk-protected entries based on liquidity sweeps</li>
                  <li>Weekly performance summaries and market breakdowns</li>
                </ul>
              </div>
              <div className="rounded-2xl border border-yellow-400/20 bg-gradient-to-br from-yellow-500/10 to-transparent p-6">
                <div className="text-sm text-yellow-200">Pro Tip</div>
                <p className="mt-3 text-sm text-gray-200">
                  Combine the bot with mentorship sessions to fast‑track consistency and decision‑making.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

