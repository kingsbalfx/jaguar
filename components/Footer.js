"use client";
import React from "react";
import Link from "next/link";
import {
  FaFacebook, FaTwitter, FaInstagram, FaLinkedin,
  FaYoutube, FaTelegram, FaTiktok, FaGlobe
} from "react-icons/fa";

const ICON_MAP = {
  facebook: FaFacebook,
  twitter: FaTwitter,
  instagram: FaInstagram,
  linkedin: FaLinkedin,
  youtube: FaYoutube,
  telegram: FaTelegram,
  tiktok: FaTiktok,
  website: FaGlobe,
};

function parseSocials(raw = "") {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    if (typeof parsed === "object") {
      return Object.entries(parsed).map(([label, url]) => ({ label, url }));
    }
  } catch {
    // fallback simple CSV
    return raw
      .split(",")
      .map((i) => i.trim())
      .filter(Boolean)
      .map((p) => {
        const [label, url] = p.includes("|") ? p.split("|") : p.split(":");
        return { label: label?.trim(), url: url?.trim() };
      });
  }
  return [];
}

export default function Footer() {
  const socials = parseSocials(process.env.NEXT_PUBLIC_SOCIALS || "");

  return (
    <footer className="w-full bg-gray-900 text-gray-400 border-t border-gray-700 mt-10">
      <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row justify-between items-center gap-6">
        <div>
          <h3 className="text-white font-bold text-2xl">KINGSBALFX</h3>
          <p className="text-sm text-gray-400">
            Forex Mentorship • VIP Signals • Premium Trading
          </p>
        </div>

        <nav className="flex flex-wrap justify-center gap-4 text-sm">
          {["About", "Privacy", "Contact", "Terms", "Policy"].map((item) => (
            <Link key={item} href={`/${item.toLowerCase()}`}>
              <span className="hover:text-white transition">{item}</span>
            </Link>
          ))}
        </nav>

        {socials.length > 0 && (
          <div className="flex gap-4">
            {socials.map((s, i) => {
              const key = s.label?.toLowerCase()?.replace(/\s+/g, "") || "";
              const Icon = ICON_MAP[key] || FaGlobe;
              return (
                <a
                  key={i}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer"
                  title={s.label}
                  aria-label={s.label}
                  className="hover:text-white transition"
                >
                  <Icon size={20} />
                </a>
              );
            })}
          </div>
        )}
      </div>

      <div className="text-center text-xs border-t border-gray-800 py-3">
        © {new Date().getFullYear()} KINGSBALFX. All rights reserved.
      </div>
    </footer>
  );
}