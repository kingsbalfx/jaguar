// components/AdSense.js
import Script from "next/script";
import { useEffect, useRef } from "react";

export default function AdSense({
  client = process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "ca-pub-9076762305803751",
  slot,
  style = {},
  format = "auto",
  responsive = true,
}) {
  const insRef = useRef(null);

  useEffect(() => {
    try {
      if (typeof window !== "undefined" && window.adsbygoogle && insRef.current) {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
      }
    } catch {
      // ignore
    }
  }, []);

  if (!slot) return null;

  return (
    <>
      <Script
        id="adsense-js"
        strategy="afterInteractive"
        src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${client}`}
        crossOrigin="anonymous"
      />
      <ins
        ref={insRef}
        className="adsbygoogle"
        style={{ display: "block", minHeight: 90, width: "100%", ...style }}
        data-ad-client={client}
        data-ad-slot={slot}
        data-ad-format={format}
        data-full-width-responsive={responsive ? "true" : "false"}
      />
    </>
  );
}
