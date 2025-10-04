import { useRouter } from "next/router";
import { useEffect } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";

const AD_EXCLUDE_PATHS = [
  "/login",
  "/register",
  "/auth/callback",
  "/admin",
  "/checkout",
  "/checkout/success",
  // exclude VIP & Premium dashboards
  "/dashboard/vip",
  "/dashboard/premium",
  // you might also want to exclude /dashboard itself if minimal
];

// same helper
function shouldShowAds(path) {
  if (!path) return false;
  for (const p of AD_EXCLUDE_PATHS) {
    // match exact or prefix
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
    <>
      {showAds && <AdsenseLoader />}

      <Component {...pageProps} />

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
    </>
  );
}
