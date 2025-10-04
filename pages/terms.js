// pages/terms.js
import React from "react";

export default function Terms() {
  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-3xl font-bold mb-6">Terms & Conditions</h1>
      <p className="mb-4">
        These Terms & Conditions govern your use of the KINGSBALFX website and services. By using our platform,
        you agree to these Terms.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Payment & Subscriptions</h2>
      <p>
        Access to Premium and VIP features requires payment via Paystack. Your plan is active only upon verified payment.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Limitation of Liability</h2>
      <p>
        KINGSBALFX is not liable for any financial losses or decisions you make using our signals or mentorship.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact</h2>
      <p>
        Questions: <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>
      </p>
    </main>
  );
}
