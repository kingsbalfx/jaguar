// pages/_document.cjs
const NextDocument = require("next/document").default;
const { Html, Head, Main, NextScript } = require("next/document");

class MyDocument extends NextDocument {
  static async getInitialProps(ctx) {
    const initialProps = await NextDocument.getInitialProps(ctx);
    return { ...initialProps };
  }

  render() {
    // We can detect the host (domain) from the request to form correct URLs
    const { req } = this.props.__NEXT_DATA__.props?.pageProps || {};
    // Fallback domain if req not available
    const defaultDomain = "kingsjaguar.vercel.app";
    const host = (req && req.headers && req.headers.host) || defaultDomain;
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || `https://${host}`;
    const canonicalUrl = `${siteUrl.replace(/\/$/, "")}/`;
    const ogImageUrl = `${siteUrl.replace(/\/$/, "")}/images/og-image.png`;

    return (
      <Html lang="en">
        <Head>
          <meta charSet="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>KINGSBALFX — Forex Mentorship & VIP Signals</title>
          <meta
            name="description"
            content="KINGSBALFX — professional forex mentorship, VIP signals, weekly lessons and 1:1 mentorship."
          />
          <meta name="robots" content="index, follow" />

          {/* Open Graph for social previews */}
          <meta property="og:title" content="KINGSBALFX — Forex Mentorship & VIP Signals" />
          <meta
            property="og:description"
            content="Weekly trading signals, VIP-only challenges, live lessons and 1:1 mentorship."
          />
          <meta property="og:type" content="website" />
          <meta property="og:url" content={canonicalUrl} />
          <meta property="og:image" content={ogImageUrl} />

          {/* Twitter card */}
          <meta name="twitter:card" content="summary_large_image" />
          <meta name="twitter:site" content="@YourTwitterHandle" />

          {/* existing tags you already had */}
          <meta name="google-adsense-account" content="ca-pub-9076762305803751" />
          <link rel="manifest" href="/manifest.json" />
          <meta name="theme-color" content="#071022" />

          {/* If you have analytics or script tags, keep them here */}
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}

module.exports = MyDocument;
