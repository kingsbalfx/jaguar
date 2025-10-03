// pages/terms.js
import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";

export default function Terms() {
  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
        <h1 className="text-3xl font-bold mb-6">Terms & Conditions</h1>
        <p className="mb-4">
          Welcome to KINGSBALFX. These terms govern your use of our website, services, and content.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">1. Acceptance of Terms</h2>
        <p>You agree to abide by these terms by using our services.</p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">2. Service Use</h2>
        <p>
          You may use our signals, mentorship, and content in compliance with local laws. You accept all risks associated
          with forex trading.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">3. Payments & Refunds</h2>
        <p>
          Premium and VIP plans require payment via Paystack. Refunds, if any, are subject to our policy (which you may define).
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">4. Changes to Terms</h2>
        <p>We reserve the right to update these terms; changes become effective when posted.</p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">5. Contact</h2>
        <p>
          For any questions about these terms, contact us at 
          <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600"> shafiuabdullahi.sa3@gmail.com</a>.
        </p>
      </main>
      <Footer />
    </>
  );
}
