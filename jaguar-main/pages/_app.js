import "../styles/globals.css";
import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";

export default function MyApp({ Component, pageProps }) {
  const router = useRouter();
  const showCandle =
    router.pathname.startsWith("/admin") || router.pathname.startsWith("/dashboard");

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
          content="Join KINGSBALFX today - access VIP and premium trading insights to grow your portfolio."
        />
        <meta property="og:image" content="https://kingsbalfx.name.ng/jaguar.png" />

        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          name="twitter:description"
          content="Join KINGSBALFX today - access VIP and premium trading insights to grow your portfolio."
        />
        <meta name="twitter:image" content="https://kingsbalfx.name.ng/jaguar.png" />
      </Head>

      <Header />

      <main className="flex-grow app-bg relative overflow-hidden">
        {showCandle && <div className="candle-backdrop" aria-hidden="true" />}
        <div className="app-content">
          <Component {...pageProps} />
        </div>
      </main>

      <Footer />
    </div>
  );
}
