import "../styles/globals.css";
import Head from "next/head";
import Script from "next/script";
import { useRouter } from "next/router";
import Header from "../components/Header";
import Footer from "../components/Footer";

const NO_ADS_PATHS = [
  "/login",
  "/register",
  "/auth/callback",
  "/complete-profile",
  "/admin",
  "/checkout",
  "/checkout/success",
  "/dashboard",
  "/dashboard/vip",
  "/dashboard/premium",
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
      </Head>

      {/* ✅ Load AdSense script only when allowed */}
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
      </main>

      <Footer />

      {/* ✅ Display your actual 728x90 ad only on approved pages */}
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
              __html: `
                (adsbygoogle = window.adsbygoogle || []).push({});
              `,
            }}
          />
        </div>
      )}
    </div>
  );
}
