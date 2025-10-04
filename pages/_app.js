// pages/_app.js
import "../styles/globals.css";
import Head from "next/head";
import { useRouter } from "next/router";
import { useEffect } from "react";

const AD_EXCLUDE_PATHS = [
  "/login",
  "/register",
  "/auth/callback",
  "/admin",
  "/checkout",
  "/checkout/success",
  "/dashboard/vip",
  "/dashboard/premium",
  // optionally exclude /dashboard if you don't want ads there
];

function shouldShowAds(path) {
  if (!path) return false;
  for (const p of AD_EXCLUDE_PATHS) {
    if (p.endsWith("/")) {
      if (path.startsWith(p)) return false;
    } else {
      if (path === p || path.startsWith(p + "/")) return false;
    }
  }
  return true;
}

function AdsenseLoader() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!document.querySelector('script[data-adsense]')) {
      const s = document.createElement("script");
      s.setAttribute("data-adsense", "true");
      s.async = true;
      s.crossOrigin = "anonymous";
      s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9076762305803751";
      document.head.appendChild(s);
    }
  }, []);
  return null;
}

export default function MyApp({ Component, pageProps }) {
  const router = useRouter();
  const showAds = shouldShowAds(router.pathname);

  return (
    <div className="min-h-screen flex flex-col bg-black text-white">
      <Head>
        <title>KINGSBALFX</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#071022" />
        <meta name="google-adsense-account" content="ca-pub-9076762305803751" />
      </Head>

      {showAds && <AdsenseLoader />}

      <Header />

      <main className="flex-grow app-bg">
        <Component {...pageProps} />
      </main>

      <Footer />

      {showAds && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 24 }}>
          <ins
            className="adsbygoogle"
            style={{ display: "block", width: 320, height: 100 }}
            data-ad-client="ca-pub-9076762305803751"
            data-ad-slot="YOUR_AD_SLOT_ID"
            data-ad-format="auto"
            data-full-width-responsive="true"
          />
          <script
            dangerouslySetInnerHTML={{
              __html: `(adsbygoogle = window.adsbygoogle || []).push({});`,
            }}
          />
        </div>
      )}
    </div>
  );
}
