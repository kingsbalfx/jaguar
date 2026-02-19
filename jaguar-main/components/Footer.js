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

function buildSocials() {
  const raw = process.env.NEXT_PUBLIC_SOCIALS || "";
  const parsed = parseSocials(raw);
  if (parsed.length > 0) return parsed;

  const mapping = [
    { label: "Twitter", value: process.env.NEXT_PUBLIC_SOCIAL_TWITTER },
    { label: "Instagram", value: process.env.NEXT_PUBLIC_SOCIAL_INSTAGRAM },
    { label: "YouTube", value: process.env.NEXT_PUBLIC_SOCIAL_YOUTUBE },
    { label: "Facebook", value: process.env.NEXT_PUBLIC_SOCIAL_FACEBOOK },
    { label: "Telegram", value: process.env.NEXT_PUBLIC_SOCIAL_TELEGRAM },
    { label: "TikTok", value: process.env.NEXT_PUBLIC_SOCIAL_TIKTOK },
    { label: "Website", value: process.env.NEXT_PUBLIC_SOCIAL_WEBSITE },
  ];

  return mapping
    .filter((item) => item.value)
    .map((item) => ({ label: item.label, url: item.value }));
}

export default function Footer() {
  const socials = buildSocials();

  return (
    <footer className="w-full bg-slate-950/90 text-gray-400 border-t border-white/10">
      <div className="h-px w-full bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent" />
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
