// pages/pricing.js
import React from "react";

export default function Pricing() {
  const plans = [
    {
      id: "trial",
      title: "Trial",
      price: "Free",
      bullets: ["Lite signals", "Weekly lessons"],
    },
    {
      id: "premium",
      title: "Premium",
      price: "₦70,000",
      bullets: [
        "Full signals",
        "Community access",
        // you can add more features here
      ],
    },
    {
      id: "vip",
      title: "VIP",
      price: "₦150,000",
      bullets: [
        "1:1 mentorship",
        "Priority support",
        // you can add more features here
      ],
    },
  ];

  return (
    <>
      <Header />
      <main
        id="maincontent"
        role="main"
        className="container mx-auto px-6 py-12"
      >
        <h1 className="text-3xl font-bold mb-6">Pricing</h1>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((p) => (
            <div
              key={p.id}
              className="border rounded-lg p-6 bg-white/5 flex flex-col"
            >
              <h2 className="text-xl font-semibold mb-4">{p.title}</h2>
              <div className="text-2xl font-extrabold mb-4">{p.price}</div>
              <ul className="mb-6 flex-1">
                {p.bullets.map((b) => (
                  <li key={b} className="text-sm mb-1">
                    • {b}
                  </li>
                ))}
              </ul>
              <a
                href="/register"
                className="inline-block w-full text-center py-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white"
                aria-label={`Choose ${p.title} plan`}
              >
                Choose {p.title}
              </a>
            </div>
          ))}
        </div>
      </main>
      <Footer />
    </>
  );
}
