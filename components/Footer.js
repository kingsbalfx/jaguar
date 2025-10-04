// components/Footer.js
import React from "react";
import Link from "next/link";
import {
  FaFacebook,
  FaTwitter,
  FaInstagram,
  FaLinkedin,
  FaYoutube,
  FaTelegram,
  FaTiktok,
  FaLink,
} from "react-icons/fa";

const ICON_MAP = {
  facebook: FaFacebook,
  twitter: FaTwitter,
  instagram: FaInstagram,
  linkedin: FaLinkedin,
  youtube: FaYoutube,
  telegram: FaTelegram,
  tiktok: FaTiktok,
};

function parseSocials(raw = "") {
  const trimmed = (raw || "").trim();
  if (!trimmed) return [];

  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      return parsed
        .map((p) => {
          if (!p) return null;
          const label = (p.label || p.name || p.title || "").toString().trim();
          const url = (p.url || p.href || p.link || "").toString().trim();
          if (!label || !url) return null;
          return { label, url };
        })
        .filter(Boolean);
    } else if (typeof parsed === "object" && parsed !== null) {
      return Object.entries(parsed)
        .map(([k, v]) => ({
          label: (k || "").toString().trim(),
          url: (v || "").toString().trim(),
        }))
        .filter((s) => s.label && s.url);
    }
  } catch (e) {
    // fall back to CSV parsing
  }

  const items = trimmed.split(",").map((p) => p.trim()).filter(Boolean);
  const out = items
    .map((item) => {
      if (item.includes("|")) {
        const [label, ...rest] = item.split("|");
        return { label: (label || "").trim(), url: (rest.join("|") || "").trim() };
      }
      if (item.includes(":")) {
        const [name, ...rest] = item.split(":");
        return { label: (name || "").trim(), url: (rest.join(":") || "").trim() };
      }
      return null;
    })
    .filter(Boolean)
    .filter((s) => s.label && s.url);

  return out;
}

export default function Footer() {
  const raw = process.env.NEXT_PUBLIC_SOCIALS || "";
  const socials = parseSocials(raw);

  return (
    <footer className="w-full bg-gray-900 text-gray-300 mt-12 border-t border-gray-700 pt-8 pb-4">
      <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-start md:items-center space-y-6 md:space-y-0">
        {/* Branding & tagline */}
        <div className="flex flex-col">
          <div className="font-bold text-2xl text-white">KINGSBALFX</div>
          <div className="text-sm text-gray-400 mt-1">
            Forex mentorship • Signals • VIP challenges
          </div>
        </div>

        {/* Navigation Links */}
        <div>
          <div className="flex flex-wrap gap-4 justify-start md:justify-center">
            <Link href="/about">
              <a className="hover:text-white transition-colors">About</a>
            </Link>
            <Link href="/privacy">
              <a className="hover:text-white transition-colors">Privacy</a>
            </Link>
            <Link href="/contact">
              <a className="hover:text-white transition-colors">Contact</a>
            </Link>
            <Link href="/terms">
              <a className="hover:text-white transition-colors">Terms</a>
            </Link>
            <Link href="/policy">
              <a className="hover:text-white transition-colors">Policy</a>
            </Link>
          </div>
        </div>

        {/* Social icons */}
        {socials.length > 0 && (
          <div className="flex gap-4">
            {socials.map((s, i) => {
              const key = (s.label || `link${i}`).toLowerCase();
              const normKey = key.replace(/\s+/g, "").replace(/[^a-z0-9]/gi, "");
              const Icon = ICON_MAP[normKey] || ICON_MAP[key] || FaLink;
              return (
                <a
                  key={i}
                  href={s.url}
                  className="text-gray-400 hover:text-white transition-colors"
                  target="_blank"
                  rel="noreferrer noopener"
                  title={s.label}
                >
                  <Icon size={20} />
                </a>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom copyright / notice */}
      <div className="mt-6 border-t border-gray-700 pt-4 text-center text-xs text-gray-500">
        &copy; {new Date().getFullYear()} KINGSBALFX. All rights reserved.
      </div>
    </footer>
  );
}

