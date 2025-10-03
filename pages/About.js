// pages/about.js
import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";

export default function About() {
  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
        <h1 className="text-3xl font-bold mb-6">About KINGSBALFX</h1>
        <p className="mb-4">
          KINGSBALFX is a professional Forex mentorship program offering curated signals, trading lessons, 1:1 mentorship,
          and VIP challenges to help traders grow and maximize their profits.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">Our Mission</h2>
        <p>
          Our mission is to empower forex traders worldwide with educational resources, accurate signals,
          responsive community support, and personalized mentorship.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">Contact & Support</h2>
        <p>
          You can email our team at <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>
          or reach us via WhatsApp at <a href="tel:+2347087316069" className="text-indigo-600">+234 708 731 6069</a>.
        </p>
      </main>
      <Footer />
    </>
  );
}
