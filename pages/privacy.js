// pages/privacy.js
import React from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";

export default function Privacy() {
  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
        <h1 className="text-3xl font-bold mb-6">Privacy Policy</h1>
        <p className="mb-4">
          At KINGSBALFX, we are committed to protecting your privacy. This Privacy Policy explains how we collect,
          use, disclose, and safeguard your information when you visit our website.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">Information We Collect</h2>
        <p>
          We may collect personal information you provide (name, email), usage data, cookies, and analytics information.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">How We Use Information</h2>
        <ul className="list-disc list-inside">
          <li>To provide and maintain services.</li>
          <li>To communicate with you (updates, emails).</li>
          <li>To analyze usage and improve our platform.</li>
        </ul>

        <h2 className="text-2xl font-semibold mt-6 mb-2">Disclosure of Information</h2>
        <p>
          We will not sell your personal data. We may share with trusted service providers under confidentiality.
        </p>

        <h2 className="text-2xl font-semibold mt-6 mb-2">Contact Us</h2>
        <p>
          For privacy-related inquiries, email: <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>
        </p>
      </main>
      <Footer />
    </>
  );
}
