import "../styles/globals.css";
import Head from "next/head";
import Script from "next/script";
import { useRouter } from "next/router";
import Header from "../components/Header";
import Footer from "../components/Footer";

const NO_ADS_PATHS = [
  "/login",
  "/register",
  "/auth",
  "/auth/callback",
  "/complete-profile",
  "/admin",
  "/checkout",
  "/checkout/success",
  "/dashboard",
  "/dashboard/vip",
  "/dashboard/premium",
  "/dashboard/pro",
  "/dashboard/lifetime",
];

function shouldShowAds(path) {
  if (!path) return false;
  return !NO_ADS_PATHS.some((p) => path === p || path.startsWith(p + "/"));
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

        {/* ✅ Jaguar logo setup */}
        <link rel="icon" href="/jaguar.png" />
        <link rel="apple-touch-icon" href="/jaguar.png" />
        <meta name="title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          name="description"
          content="KINGSBALFX — professional forex and crypto trading solutions for serious investors."
        />

        {/* ✅ Open Graph (Facebook, WhatsApp, etc.) */}
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://kingsbalfx.name.ng/" />
        <meta property="og:title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          property="og:description"
          content="Join KINGSBALFX today — access VIP and premium trading insights to grow your portfolio."
        />
        <meta property="og:image" content="https://kingsbalfx.name.ng/jaguar.png" />

        {/* ✅ Twitter Card (for X / Twitter link previews) */}
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content="KINGSBALFX - Trade Smart, Live Smart" />
        <meta
          name="twitter:description"
          content="Join KINGSBALFX today — access VIP and premium trading insights to grow your portfolio."
        />
        <meta name="twitter:image" content="https://kingsbalfx.name.ng/jaguar.png" />
      </Head>

      {/* ✅ Load Google AdSense only where allowed */}
      {showAds && (
        <Script
          id="adsense-script"
          async
          strategy="afterInteractive"
          crossOrigin="anonymous"
          src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9076762305803751"
        />
      )}

      <Header />

      <main className="flex-grow app-bg">
        <div className="app-content">
          <Component {...pageProps} />
        </div>

        {/* ✅ Responsive AdSense block */}
        {showAds && (
          <div style={{ display: "flex", justifyContent: "center", margin: "24px 0" }}>
            <ins
              className="adsbygoogle"
              style={{ display: "block" }}
              data-ad-client="ca-pub-9076762305803751"
              data-ad-slot="1636184407"
              data-ad-format="auto"
              data-full-width-responsive="true"
            ></ins>
            <Script
              id="adsbygoogle-responsive"
              strategy="afterInteractive"
              dangerouslySetInnerHTML={{
                __html: `(adsbygoogle = window.adsbygoogle || []).push({});`,
              }}
            />
          </div>
        )}
      </main>

      <Footer />

      {/* ✅ Fixed 728x90 banner for desktop view */}
      {showAds && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: 24 }}>
          <ins
            className="adsbygoogle"
            style={{ display: "inline-block", width: 728, height: 90 }}
            data-ad-client="ca-pub-9076762305803751"
            data-ad-slot="1636184407"
          ></ins>
          <Script
            id="adsbygoogle-init"
            strategy="afterInteractive"
            dangerouslySetInnerHTML={{
              __html: `(adsbygoogle = window.adsbygoogle || []).push({});`,
            }}
          />
        </div>
      )}
    </div>
  );
}
