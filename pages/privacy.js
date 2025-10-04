import React from "react";

export default function Privacy() {
  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-3xl font-bold mb-6">Privacy Policy</h1>
      <p className="mb-4">
        This Privacy Policy describes how KINGSBALFX (“we”, “our”, “us”) handles and protects your personal data when
        you use our website and mentorship services.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Information We Collect</h2>
      <p>
        We collect information such as your name, email, and usage data when you sign up, interact with our services, or
        make payments.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">How We Use Your Information</h2>
      <ul className="list-disc list-inside">
        <li>To personalize your experience and improve our services.</li>
        <li>To send trading updates, mentorship notifications, and course materials.</li>
        <li>To monitor usage and prevent fraud or misuse.</li>
      </ul>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Data Protection</h2>
      <p>
        We implement security measures to safeguard your personal information. However, no method of transmission
        over the Internet is 100% secure.
      </p>

      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact</h2>
      <p>
        For privacy inquiries, contact{" "}
        <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">
          shafiuabdullahi.sa3@gmail.com
        </a>.
      </p>
    </main>
  );
}
