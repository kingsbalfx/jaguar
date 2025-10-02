// components/AdSense.js
import Script from "next/script";
import { useEffect } from "react";

/**
 * Minimal AdSense component for Next.js pages.
 * - Replace CLIENT with your ca-pub-... publisher id
 * - Optionally pass slot prop if you have a specific ad unit id
 */
export default function AdSense({ client = "ca-pub-REPLACE_WITH_YOURS", slot = "" }) {
  useEffect(() => {
    // If the script is already loaded, request ad refresh
    try {
      if (window && window.adsbygoogle) {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    } catch (e) {
      // ignore
    }
  }, []);

  return (
    <>
      {/* Loads AdSense library only when this component is rendered */}
      <Script
        id="adsense-script"
        strategy="afterInteractive"
        src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${client}`}
        crossOrigin="anonymous"
      />
      {/* responsive ad slot — will display only on pages using <AdSense /> */}
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </>
  );
}
