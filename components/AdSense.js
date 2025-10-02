// components/AdSense.js
import Script from "next/script";
import { useEffect } from "react";

/**
 * AdSense component
 * - default client = your publisher id
 * - pass slot prop if you have a specific ad unit id (optional)
 *
 * Usage:
 * <AdSense slot="1234567890" />
 */
export default function AdSense({
  client = "ca-pub-9076762305803751",
  slot = ""
}) {
  useEffect(() => {
    // If the script has already loaded, request adsbygoogle to render this <ins>
    try {
      if (typeof window !== "undefined" && window.adsbygoogle) {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    } catch (err) {
      // swallow errors quietly
      // console.error("adsense push error", err);
    }
  }, []);

  return (
    <>
      {/* Load AdSense lib only when this component is used */}
      <Script
        id="adsense-js"
        strategy="afterInteractive"
        src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9076762305803751`}
        crossOrigin="anonymous"
      />
      {/* Responsive ad container */}
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client="ca-pub-9076762305803751"
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </>
  );
}
