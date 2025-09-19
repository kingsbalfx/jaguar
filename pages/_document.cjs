// pages/_document.cjs

const NextDocument = require('next/document').default;
const { Html, Head, Main, NextScript } = require('next/document');

class MyDocument extends NextDocument {
  static async getInitialProps(ctx) {
    const initialProps = await NextDocument.getInitialProps(ctx);
    return { ...initialProps };
  }

  render() {
    return (
      <Html lang="en">
        <Head>
          <meta name="google-adsense-account" content="ca-pub-9076762305803751" />
          <script
            async
            src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9076762305803751"
            crossOrigin="anonymous"
          ></script>
          <link rel="manifest" href="/manifest.json" />
          <meta name="theme-color" content="#071022" />
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
