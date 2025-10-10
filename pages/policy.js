// pages/policy.js
import React from "react";

export default function Policy() {
  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white">
      <h1 className="text-3xl font-bold mb-6">Platform Policy</h1>
      <p className="mb-4">
        KINGSBALFX maintains strict policies to ensure professionalism, transparency, and fairness within our trading mentorship community.
      </p>
      <h2 className="text-2xl font-semibold mt-6 mb-2">Community Conduct</h2>
      <ul className="list-disc list-inside">
        <li>Respect all members and mentors.</li>
        <li>No sharing of paid content outside authorized channels.</li>
        <li>Any misuse or abuse may result in account suspension.</li>
      </ul>
      <h2 className="text-2xl font-semibold mt-6 mb-2">Refund Policy</h2>
      <p>Payments made for VIP or Premium mentorship programs are non-refundable after access has been granted.</p>
      <h2 className="text-2xl font-semibold mt-6 mb-2">Updates</h2>
      <p>This policy may be updated periodically. Continued use of our services means you accept the latest version.</p>
      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact</h2>
      <p>
        Reach out at{" "}
        <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">
          shafiuabdullahi.sa3@gmail.com
        </a>.
      </p>
    </main>
  );
}