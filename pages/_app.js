// pages/_app.js
import '../styles/globals.css'
import Head from 'next/head'
import Script from 'next/script'

function MyApp({ Component, pageProps }) {
  return (
    <>
      <Head>
        <title>KINGSBALFX</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#071022" />
      </Head>

      {/* Google ads script - load client-side */}
      <Script
        src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-9076762305803751"
        strategy="afterInteractive"
        crossOrigin="anonymous"
        async
      />

      <div className="min-h-screen app-bg text-white">
        <Component {...pageProps} />
      </div>
    </>
  )
}
export default MyApp
