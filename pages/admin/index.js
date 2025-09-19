import React, { useState } from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import Link from "next/link";

export default function Admin() {
  const [menuOpen, setMenuOpen] = useState(true);
  const [selected, setSelected] = useState("overview");

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8">
        <div className="flex gap-6">
          <aside
            className={
              "w-64 p-4 rounded-lg bg-black/30 " + (menuOpen ? "" : "hidden")
            }
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-bold">Admin</h3>
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="text-sm"
              >
                Toggle
              </button>
            </div>
            <ul className="flex flex-col gap-2">
              <li>
                <button
                  onClick={() => setSelected("overview")}
                  className="w-full text-left"
                >
                  Overview
                </button>
              </li>
              <li>
                <button
                  onClick={() => setSelected("users")}
                  className="w-full text-left"
                >
                  Users & Segments
                </button>
              </li>
              <li>
                <button
                  onClick={() => setSelected("mentorship")}
                  className="w-full text-left"
                >
                  Mentorship Dashboard
                </button>
              </li>
              <li>
                <button
                  onClick={() => setSelected("subscriptions")}
                  className="w-full text-left"
                >
                  Subscriptions
                </button>
              </li>
              <li>
                <Link href="/admin/messages" className="text-sm text-gray-300">
                  Messages Manager
                </Link>
              </li>
            </ul>
          </aside>

          <section className="flex-1 p-4 bg-black/20 rounded-lg">
            {selected === "overview" && (
              <div>
                <h2 className="text-2xl font-bold mb-4">Overview</h2>
                <p className="text-gray-300">
                  Quick metrics and content overview will appear here (total
                  users, revenue, active sessions...)
                </p>
              </div>
            )}

            {selected === "users" && (
              <div>
                <h2 className="text-2xl font-bold mb-4">Users & Segments</h2>
                <p className="text-gray-300">
                  List, filter, edit user segmentation (premium / vip / trial) —
                  implemented via Supabase user metadata.
                </p>
              </div>
            )}

            {selected === "mentorship" && (
              <div>
                <h2 className="text-2xl font-bold mb-4">
                  Mentorship Dashboard
                </h2>
                <p className="text-gray-300">
                  Manage course content, lessons (video/audio/doc), challenges,
                  trading signals, and community segmentation.
                </p>
              </div>
            )}

            {selected === "subscriptions" && (
              <div>
                <h2 className="text-2xl font-bold mb-4">Subscription Status</h2>
                <p className="text-gray-300">
                  VIP / Premium subscription statuses, webhook logs, and manual
                  adjustments.
                </p>
              </div>
            )}
          </section>
        </div>
      </main>
      <Footer />
    </>
  );
}
