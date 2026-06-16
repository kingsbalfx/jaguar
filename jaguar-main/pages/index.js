// pages/index.js
import React, { useEffect, useState } from "react";
import Link from "next/link";
import AdSense from "../components/AdSense";
import { getSupabaseClient } from "../lib/supabaseClient";
import dynamic from "next/dynamic";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { PRICING_TIERS, formatPrice } from "../lib/pricing-config";
import { useRouter } from "next/router";
import EmbeddedLivePlayer from "../components/EmbeddedLivePlayer";

const WebRTCRoom = dynamic(() => import("../components/WebRTCRoom"), {
  ssr: false,
});

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
    return {
      props: {
        initialMessages: [],
        liveSession: null,
        canViewLive: false,
        isAuthenticated: Boolean(session?.user),
      },
    };
  }

  try {
    const { data, error } = await fetchMessagesWithFallback(supabaseAdmin);
    if (error) {
      console.error("Landing messages error:", error);
      return {
        props: {
          initialMessages: [],
          liveSession: null,
          canViewLive: false,
          isAuthenticated: Boolean(session?.user),
        },
      };
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
    const subscriberRoles = new Set([
      "premium",
      "vip",
      "pro",
      "lifetime",
      "admin",
    ]);
    const canViewLive =
      Boolean(session?.user) &&
      subscriberRoles.has(viewerRole) &&
      (liveSession
        ? Array.isArray(liveSession.target_user_ids) &&
          liveSession.target_user_ids.length
          ? liveSession.target_user_ids.includes(session.user.id) ||
            viewerRole === "admin"
          : canAccess(viewerRole, liveSession.segment || "all")
        : false);

    return {
      props: {
        initialMessages: data || [],
        liveSession,
        canViewLive,
        isAuthenticated: Boolean(session?.user),
      },
    };
  } catch (err) {
    console.error("Landing messages error:", err);
    return {
      props: {
        initialMessages: [],
        liveSession: null,
        canViewLive: false,
        isAuthenticated: Boolean(session?.user),
      },
    };
  }
}

export default function Home({
  initialMessages = [],
  liveSession = null,
  canViewLive = false,
  isAuthenticated = false,
}) {
  const router = useRouter();
  const [mode, setMode] = useState("free"); // free | premium | vip | pro | lifetime
  const [currentMessages, setCurrentMessages] = useState(initialMessages);
  const [currentLiveSession, setCurrentLiveSession] = useState(liveSession);
  const [currentCanViewLive, setCurrentCanViewLive] = useState(canViewLive);
  const [currentIsAuthenticated, setCurrentIsAuthenticated] = useState(isAuthenticated);
  const [liveDisplayName, setLiveDisplayName] = useState("Subscriber");

  useEffect(() => {
    let active = true;
    const refreshLandingUpdates = async () => {
      try {
        const response = await fetch("/api/landing-updates", { cache: "no-store" });
        const data = await response.json();
        if (!active || !response.ok) return;
        setCurrentMessages(Array.isArray(data.messages) ? data.messages : []);
        setCurrentLiveSession(data.liveSession || null);
        setCurrentCanViewLive(Boolean(data.canViewLive));
        setCurrentIsAuthenticated(Boolean(data.isAuthenticated));
        setLiveDisplayName(data.displayName || "Subscriber");
      } catch {
        // Keep server-rendered content when a refresh is unavailable.
      }
    };
    refreshLandingUpdates();
    const timer = window.setInterval(refreshLandingUpdates, 30000);
    window.addEventListener("focus", refreshLandingUpdates);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshLandingUpdates);
    };
  }, []);

  const defaultMessages = [
    {
      id: 1,
      text: "Precision entries. Disciplined exits. Every signal measured.",
      segments: ["all"],
    },
    {
      id: 2,
      text: "VIP weekly trade reviews are live with full market walkthroughs.",
      segments: ["vip"],
    },
    {
      id: 3,
      text: "New lesson drop: Market Structure & Liquidity Sweeps.",
      segments: ["premium", "vip"],
    },
    {
      id: 4,
      text: "Academy and VIP challenge sessions start this week - join the desk.",
      segments: ["premium", "vip"],
    },
    {
      id: 5,
      text: "VIP 1:1 mentorship slots open for serious traders.",
      segments: ["vip"],
    },
    {
      id: 6,
      text: "Pro tier unlocks 1:1 coaching, custom strategies, and advanced analytics.",
      segments: ["pro"],
    },
    {
      id: 7,
      text: "Lifetime members get permanent access to every update, session, and signal.",
      segments: ["lifetime"],
    },
    {
      id: 8,
      text: "Pro & Lifetime tiers include priority execution and concierge support.",
      segments: ["pro", "lifetime"],
    },
  ];
  const normalizedMessages = (
    currentMessages.length ? currentMessages : defaultMessages
  ).map((m, i) => {
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
    free: "Free access to intro lessons, risk guidance, and sample content.",
    premium: "Academy adds structured lessons, PDFs, community access, and weekly live classes.",
    vip: "VIP adds assignment review, journal review, group mentorship, and priority Q&A.",
    pro: "Pro adds private mentorship, deeper strategy correction, and personal risk review.",
    lifetime:
      "Lifetime members keep recorded lessons, PDFs, community access, and future course updates.",
  };

  const toggleStyles = {
    free: {
      color: "#fbbf24",
      border: "rgba(251, 191, 36, 0.6)",
      label: "Free Trial",
    },
    premium: {
      color: "#3b82f6",
      border: "rgba(59, 130, 246, 0.6)",
      label: "Academy",
    },
    vip: { color: "#a855f7", border: "rgba(168, 85, 247, 0.6)", label: "VIP" },
    pro: { color: "#6366f1", border: "rgba(99, 102, 241, 0.6)", label: "Pro" },
    lifetime: {
      color: "#ec4899",
      border: "rgba(236, 72, 153, 0.6)",
      label: "Lifetime",
    },
  };

  const visibleMessages = normalizedMessages.filter(
    (m) => m.segments.includes("all") || m.segments.includes(mode),
  );
  const promotionLabel = toggleStyles[mode]?.label || "KINGSBALFX";

  const tierKey = mode.toUpperCase();
  const tier = PRICING_TIERS[tierKey];
  const tierPrice =
    tier?.price === 0
      ? "Free"
      : tier
        ? formatPrice(tier.price, tier.currency)
        : "";
  const tierBadge = tier?.badge || "Access";
  const tierHighlights = tier?.features
    ? [
        `Mentorship: ${tier.features.mentorship ? "Included" : "Content access"}`,
        `Community: ${tier.features.communityAccess || "Limited"}`,
        `Assignment review: ${tier.features.assignmentReview ? "Included" : "Not included"}`,
        `Private testing: ${tier.features.privateTestingOnly ? "Controlled opt-in" : "Not included"}`,
      ]
    : [];

  const nextTarget = mode === "free" ? "/register" : `/checkout?plan=${mode}`;
  const loginUrl = `/login?next=${encodeURIComponent(nextTarget)}`;
  const accessUrl = currentIsAuthenticated ? nextTarget : loginUrl;

  return (
    <main className="flex-grow app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content landing-shell container mx-auto px-6 py-14">
        <div className="landing-hero grid gap-10 lg:grid-cols-[1.1fr_0.9fr] items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-1 text-xs uppercase tracking-widest text-indigo-200">
              KingsBalfx Trading Lab
            </div>
            <h1 className="display-font mt-4 text-4xl md:text-6xl font-bold leading-tight">
              Structured forex education and mentorship built for disciplined growth.
            </h1>
            <p className="mt-4 text-lg text-gray-300 max-w-2xl">
              Build your process with guided ICT education, disciplined risk
              controls, practical reviews, and a clear learning path.
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
            <div className="landing-metrics mt-8 grid gap-4 sm:grid-cols-3">
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

          <div className="glass-panel landing-snapshot rounded-3xl p-6 relative overflow-hidden">
            <div className="absolute -top-20 -right-24 h-48 w-48 rounded-full bg-indigo-500/20 blur-3xl" />
            <div className="absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-yellow-400/10 blur-3xl" />
            <div className="relative space-y-4">
              <div className="text-sm text-indigo-200">Live Bot Snapshot</div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Signal Quality</div>
                <div className="mt-1 text-xl font-semibold">
                  Academy Confidence
                </div>
                <p className="mt-2 text-sm text-gray-300">
                  Filters tuned to liquidity sweeps, structure shifts, and HTF
                  momentum.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Execution Layer</div>
                <div className="mt-1 text-xl font-semibold">
                  Risk‑Locked Entries
                </div>
                <p className="mt-2 text-sm text-gray-300">
                  Dynamic lot sizing with max‑trade guards and tiered exposure
                  rules.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Community</div>
                <div className="mt-1 text-xl font-semibold">
                  Mentor‑Led Rooms
                </div>
                <p className="mt-2 text-sm text-gray-300">
                  Daily breakdowns, session recaps, and accountability
                  check‑ins.
                </p>
              </div>
            </div>
          </div>
        </div>

        <section className="landing-section mt-12">
          {currentLiveSession && (
            <div className="mb-6 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-4">
              <div className="text-xs uppercase tracking-widest text-emerald-200 mb-2">
                Live Session
              </div>
              <div className="text-lg font-semibold text-white">
                {currentLiveSession.title || "Next Live Session"}
              </div>
              <div className="mt-1 text-sm text-emerald-100/80">
                {currentLiveSession.starts_at
                  ? new Date(currentLiveSession.starts_at).toLocaleString()
                  : "Time not set"}
                {currentLiveSession.ends_at
                  ? ` - ${new Date(currentLiveSession.ends_at).toLocaleTimeString()}`
                  : ""}
                {currentLiveSession.timezone ? ` (${currentLiveSession.timezone})` : ""}
              </div>
              {currentCanViewLive ? (
                <div className="mt-4">
                  {["youtube", "videosdk", "embed"].includes(
                    currentLiveSession.media_type,
                  ) &&
                    currentLiveSession.media_url && (
                      <EmbeddedLivePlayer
                        mediaType={currentLiveSession.media_type}
                        mediaUrl={currentLiveSession.media_url}
                        title={currentLiveSession.title || "Live Session"}
                      />
                    )}
                  {currentLiveSession.media_type === "webrtc" && (
                    <div className="mt-3">
                      <WebRTCRoom
                        key={currentLiveSession.room_name || currentLiveSession.id}
                        roomName={currentLiveSession.room_name || currentLiveSession.id}
                        roomTitle={currentLiveSession.title || "Live Session"}
                        displayName={liveDisplayName}
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
          <div className="tier-switcher flex flex-wrap gap-3 mb-3">
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

          {tier && (
            <div className="tier-spotlight mb-8">
              <div className="tier-spotlight__glow" aria-hidden="true" />
              <div className="tier-spotlight__content">
                <div className="tier-spotlight__badge">{tierBadge}</div>
                <div className="tier-spotlight__title">
                  {tier.displayName} Tier
                </div>
                <div className="tier-spotlight__price">{tierPrice}</div>
                <p className="tier-spotlight__desc">{tier.description}</p>
                <ul className="tier-spotlight__list">
                  {tierHighlights.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <div className="tier-spotlight__actions">
                  <button
                    onClick={() => router.push(accessUrl)}
                    className="tier-spotlight__cta"
                  >
                    {currentIsAuthenticated ? "Upgrade / Access" : "Sign in to access"}
                  </button>
                  <button
                    onClick={() => router.push("/pricing")}
                    className="tier-spotlight__secondary"
                  >
                    Compare all plans
                  </button>
                </div>
                <div className="tier-spotlight__note">
                  Double-tap a tier toggle to jump directly to sign in.
                </div>
              </div>
            </div>
          )}

          {visibleMessages.length > 0 && (
            <section className="landing-promotions" aria-label={`${promotionLabel} announcements`}>
              <div className="landing-promotions__halo landing-promotions__halo--one" aria-hidden="true" />
              <div className="landing-promotions__halo landing-promotions__halo--two" aria-hidden="true" />
              <div className="landing-promotions__header">
                <div>
                  <div className="landing-promotions__eyebrow"><span /> KINGSBALFX Desk Bulletin</div>
                  <h2>Opportunities built for your next move.</h2>
                  <p>Fresh mentorship updates, learning releases, and access announcements selected for the {promotionLabel} experience.</p>
                </div>
                <button onClick={() => router.push(accessUrl)} className="landing-promotions__header-cta">
                  {currentIsAuthenticated ? "Open my access" : "Join KINGSBALFX"}
                </button>
              </div>
              <div className="landing-promotions__grid">
                {visibleMessages.map((message, index) => (
                  <article key={message.id} className={`landing-promotion-card ${index === 0 ? "landing-promotion-card--featured" : ""}`}>
                    <div className="landing-promotion-card__top">
                      <div className="landing-promotion-card__icon" aria-hidden="true">{String(index + 1).padStart(2, "0")}</div>
                      <div className="landing-promotion-card__badge">{promotionLabel} Update</div>
                    </div>
                    <div className="landing-promotion-card__copy">{message.text}</div>
                    <div className="landing-promotion-card__footer">
                      <span>Official announcement</span>
                      <button onClick={() => router.push(accessUrl)}>Explore access <span aria-hidden="true">-&gt;</span></button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {mode === "free" && (
            <div className="mt-8 rounded-2xl border border-yellow-400/30 bg-yellow-500/5 p-4">
              <div className="text-xs uppercase tracking-widest text-yellow-300 mb-2">
                Sponsored
              </div>
              <AdSense slot="1636184407" />
            </div>
          )}
        </section>

        <section className="landing-engine mt-12 relative overflow-hidden rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-slate-950 via-indigo-950/60 to-black p-8">
          <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-yellow-400/10 blur-3xl" />

          <div className="relative grid gap-8 md:grid-cols-[1.1fr_0.9fr] items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-yellow-400/40 bg-yellow-400/10 px-3 py-1 text-xs uppercase tracking-widest text-yellow-300">
                Controlled Learning Tools
              </div>
              <h2 className="mt-4 text-3xl md:text-4xl font-bold leading-tight">
                Guided analysis, disciplined risk, and practical mentorship.
              </h2>
              <p className="mt-4 text-gray-300">
                Learn ICT structure through guided lessons and practical reviews,
                Build disciplined analysis and risk habits through guided practice,
                while Academy and VIP unlock deeper mentorship, live classes,
                and private learning room access.
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Learning Path</div>
                  <div className="mt-1 text-lg font-semibold text-white">
                    Structured Lessons
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Risk Discipline</div>
                  <div className="mt-1 text-lg font-semibold text-white">
                    Guided Reviews
                  </div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Mentorship</div>
                  <div className="mt-1 text-lg font-semibold text-white">
                    Real‑time Alerts
                  </div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/pricing">
                  <a className="px-5 py-3 rounded-lg text-white font-semibold btn-primary">
                    Explore Academy Plans
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
                  <li>Structured lessons and practical market breakdowns</li>
                  <li>Risk-management guidance and disciplined review</li>
                  <li>Weekly live classes and mentorship feedback</li>
                </ul>
              </div>
              <div className="rounded-2xl border border-yellow-400/20 bg-gradient-to-br from-yellow-500/10 to-transparent p-6">
                <div className="text-sm text-yellow-200">Pro Tip</div>
                <p className="mt-3 text-sm text-gray-200">
                  Combine the bot with mentorship sessions to fast‑track
                  consistency and decision‑making.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
