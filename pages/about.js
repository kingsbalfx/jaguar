// pages/about.js
import React from "react";

export default function About() {
  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-3xl font-bold mb-6">About KINGSBALFX</h1>
      <p className="mb-4">
        KINGSBALFX is a leading Forex mentorship platform. We provide curated trading signals, real-time analysis,
        deep market insights, personalized mentorship, and a community of committed traders.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Our Mission</h2>
      <p className="mb-4">
        Our mission is to empower aspiring and experienced forex traders by providing verified, actionable signals,
        rigorous training, continuous support, and community accountability.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">What We Offer</h2>
      <ul className="list-disc list-inside">
        <li>Daily & premium forex signals with entry, stop loss, and take profit levels.</li>
        <li>Weekly lessons and market breakdowns.</li>
        <li>1-on-1 mentorship and VIP challenges.</li>
        <li>Access to archive of trades and performance reports.</li>
      </ul>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact Us</h2>
      <p>
        Email us at <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>.
      </p>
    </main>
  );
}
