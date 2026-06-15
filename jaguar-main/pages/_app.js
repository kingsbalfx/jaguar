import "../styles/globals.css";
import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";

export default function MyApp({ Component, pageProps }) {
  const router = useRouter();
  const isAuthRoute =
    router.pathname === "/login" || router.pathname === "/register" || router.pathname.startsWith("/auth");
  const showCandle =
    router.pathname.startsWith("/admin") || router.pathname.startsWith("/dashboard");
  const showQuickNav = showCandle;

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    if (typeof window === "undefined") return;
    const flag = window.localStorage.getItem("enforce_single_session");
    if (!flag) return;
    const client = getBrowserSupabaseClient();
    if (!client) return;
    (async () => {
      try {
        const { data } = await client.auth.getSession();
        if (data?.session) {
          await client.auth.signOut({ scope: "others" });
        }
      } catch {}
      window.localStorage.removeItem("enforce_single_session");
    })();
  }, []);

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    if (typeof window === "undefined") return;
    const client = getBrowserSupabaseClient();
    if (!client) return;
    const idleLimitMs = 10 * 60 * 1000;
    let timeoutId = null;
    let sessionRefreshId = null;

    const protectedActivityActive = () =>
      Number(window.__kingsbalActiveLiveRooms || 0) > 0 ||
      Number(window.__kingsbalActiveUploads || 0) > 0;

    const resetTimer = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(async () => {
        if (protectedActivityActive()) {
          resetTimer();
          return;
        }
        try {
          const { data } = await client.auth.getSession();
          if (data?.session) {
            await client.auth.signOut();
            if (window.location.pathname !== "/login") {
              window.location.href = "/login?reason=idle";
            }
          }
        } catch {}
      }, idleLimitMs);
    };

    const refreshLiveSession = async () => {
      if (!protectedActivityActive()) return;
      try {
        await client.auth.refreshSession();
      } catch {}
      resetTimer();
    };

    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    events.forEach((evt) => window.addEventListener(evt, resetTimer));
    window.addEventListener("kingsbal:live-room-activity", resetTimer);
    window.addEventListener("kingsbal:protected-activity", resetTimer);
    sessionRefreshId = window.setInterval(refreshLiveSession, 20 * 60 * 1000);
    resetTimer();

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (sessionRefreshId) window.clearInterval(sessionRefreshId);
      events.forEach((evt) => window.removeEventListener(evt, resetTimer));
      window.removeEventListener("kingsbal:live-room-activity", resetTimer);
      window.removeEventListener("kingsbal:protected-activity", resetTimer);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-black text-white">
      <Head>
        <title>KINGSBALFX</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#071022" />
        <meta name="google-adsense-account" content="ca-pub-9076762305803751" />

        <link rel="icon" href="/jaguar.png" />
        <link rel="apple-touch-icon" href="/jaguar.png" />
        <meta name="title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          name="description"
          content="KINGSBALFX - professional forex and crypto trading solutions for serious investors."
        />

        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://kingsbalfx.name.ng/" />
        <meta property="og:title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          property="og:description"
          content="Join KINGSBALFX Academy for structured forex education, mentorship, and risk-management guidance."
        />
        <meta property="og:image" content="https://kingsbalfx.name.ng/jaguar.png" />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          name="twitter:description"
          content="Join KINGSBALFX Academy for structured forex education, mentorship, and risk-management guidance."
        />
        <meta name="twitter:image" content="https://kingsbalfx.name.ng/jaguar.png" />
      </Head>

      <Header />

      <main className={`flex-grow app-bg relative overflow-x-hidden${isAuthRoute ? " auth-main" : ""}`}>
        {showCandle && <div className="candle-backdrop" aria-hidden="true" />}
        <div className={`app-content${showQuickNav ? " with-quicknav" : ""}`}>
          <Component {...pageProps} />
        </div>
      </main>

      {!isAuthRoute && <Footer />}
    </div>
  );
}
