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
    // fall through to CSV parsing
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
    <footer className="w-full py-6 bg-black text-white mt-12">
      <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-center">
        <div>
          <div className="font-bold text-lg">KINGSBALFX</div>
          <div className="text-sm text-gray-300">
            Forex mentorship • Signals • VIP challenges
          </div>
        </div>

        {/* Navigation / Important Links */}
        <div className="mt-4 md:mt-0">
          <div className="flex gap-4">
            <Link href="/about">
              <a className="text-gray-200 hover:underline">About</a>
            </Link>
            <Link href="/privacy">
              <a className="text-gray-200 hover:underline">Privacy</a>
            </Link>
            <Link href="/contact">
              <a className="text-gray-200 hover:underline">Contact</a>
            </Link>
            <Link href="/terms">
              <a className="text-gray-200 hover:underline">Terms</a>
            </Link>
          </div>
        </div>

        {/* Social links: only render when there are socials */}
        {socials.length > 0 && (
          <div className="mt-4 md:mt-0">
            <div className="flex gap-4 items-center">
              {socials.map((s, i) => {
                const key = (s.label || `link${i}`).toLowerCase();
                const normKey = key.replace(/\s+/g, "").replace(/[^a-z0-9]/gi, "");
                const Icon = ICON_MAP[normKey] || ICON_MAP[key] || FaLink;

                return (
                  <a
                    key={i}
                    href={s.url}
                    className="text-gray-200 hover:underline inline-flex items-center gap-2"
                    target="_blank"
                    rel="noreferrer noopener"
                    title={s.label}
                  >
                    <Icon />
                    <span className="hidden sm:inline">{s.label}</span>
                  </a>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </footer>
  );
}
