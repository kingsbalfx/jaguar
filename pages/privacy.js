// pages/privacy.js
import React from "react";

export default function Privacy() {
  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-3xl font-bold mb-6">Privacy Policy</h1>
      <p className="mb-4">
        This Privacy Policy describes how KINGSBALFX (“we”, “our”, “us”) handles, collects, and uses personal information
        when you access our website or services.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Information We Collect</h2>
      <p>
        We collect information you provide (e.g. email address when you sign up), usage data (pages visited, timestamps), cookies and analytics data.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">How We Use Information</h2>
      <ul className="list-disc list-inside">
        <li>To improve and personalize your user experience.</li>
        <li>To send updates, newsletters, or notifications.</li>
        <li>To analyze and monitor site traffic and trends.</li>
      </ul>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact</h2>
      <p>
        If you have questions about privacy, email <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>.
      </p>
    </main>
  );
}
