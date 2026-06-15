import React from "react";
import Link from "next/link";
import {
  FaFacebook, FaTwitter, FaInstagram, FaLinkedin, FaYoutube,
  FaTelegram, FaTiktok, FaGlobe, FaWhatsapp,
} from "react-icons/fa";

const ICON_MAP = {
  facebook: FaFacebook,
  twitter: FaTwitter,
  x: FaTwitter,
  instagram: FaInstagram,
  linkedin: FaLinkedin,
  youtube: FaYoutube,
  telegram: FaTelegram,
  whatsapp: FaWhatsapp,
  tiktok: FaTiktok,
  website: FaGlobe,
};

function normalizeSocialUrl(value, label = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^(https?:\/\/|mailto:|tel:)/i.test(raw)) return raw;
  if (raw.startsWith("@")) {
    const handle = raw.slice(1);
    const platform = String(label).toLowerCase();
    if (platform.includes("telegram")) return `https://t.me/${handle}`;
    if (platform.includes("twitter") || platform === "x") return `https://x.com/${handle}`;
    if (platform.includes("instagram")) return `https://instagram.com/${handle}`;
    if (platform.includes("tiktok")) return `https://tiktok.com/@${handle}`;
  }
  return `https://${raw.replace(/^\/+/, "")}`;
}

function parseSocials(raw = "") {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.map((item) => ({ ...item, url: normalizeSocialUrl(item.url || item.value, item.label) }));
    if (parsed && typeof parsed === "object") {
      return Object.entries(parsed).map(([label, url]) => ({ label, url: normalizeSocialUrl(url, label) }));
    }
  } catch {
    return raw.split(",").map((item) => item.trim()).filter(Boolean).map((pair) => {
      if (/^https?:\/\//i.test(pair)) return { label: "Website", url: pair };
      const separator = pair.includes("|") ? "|" : ":";
      const separatorIndex = pair.indexOf(separator);
      const label = separatorIndex >= 0 ? pair.slice(0, separatorIndex).trim() : "Website";
      const url = separatorIndex >= 0 ? pair.slice(separatorIndex + 1).trim() : pair;
      return { label, url: normalizeSocialUrl(url, label) };
    });
  }
  return [];
}

function buildSocials() {
  const parsed = parseSocials(process.env.NEXT_PUBLIC_SOCIALS || "");
  const mapping = parsed.length ? parsed : [
    { label: "Twitter", value: process.env.NEXT_PUBLIC_SOCIAL_TWITTER || process.env.NEXT_PUBLIC_TWITTER_URL },
    { label: "Instagram", value: process.env.NEXT_PUBLIC_SOCIAL_INSTAGRAM || process.env.NEXT_PUBLIC_INSTAGRAM_URL },
    { label: "YouTube", value: process.env.NEXT_PUBLIC_SOCIAL_YOUTUBE || process.env.NEXT_PUBLIC_YOUTUBE_URL },
    { label: "Facebook", value: process.env.NEXT_PUBLIC_SOCIAL_FACEBOOK || process.env.NEXT_PUBLIC_FACEBOOK_URL },
    { label: "LinkedIn", value: process.env.NEXT_PUBLIC_SOCIAL_LINKEDIN || process.env.NEXT_PUBLIC_LINKEDIN_URL },
    { label: "Telegram", value: process.env.NEXT_PUBLIC_SOCIAL_TELEGRAM || process.env.NEXT_PUBLIC_TELEGRAM_URL },
    { label: "WhatsApp", value: process.env.NEXT_PUBLIC_SOCIAL_WHATSAPP || process.env.NEXT_PUBLIC_WHATSAPP_URL },
    { label: "TikTok", value: process.env.NEXT_PUBLIC_SOCIAL_TIKTOK || process.env.NEXT_PUBLIC_TIKTOK_URL },
    { label: "Website", value: process.env.NEXT_PUBLIC_SOCIAL_WEBSITE || process.env.NEXT_PUBLIC_WEBSITE_URL },
  ];
  const seen = new Set();
  return mapping.map((item) => ({ label: item.label, url: normalizeSocialUrl(item.url || item.value, item.label) })).filter((item) => {
    const key = `${item.label}:${item.url}`.toLowerCase();
    if (!item.url || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export default function Footer() {
  const socials = buildSocials();
  return (
    <footer className="w-full border-t border-white/10 bg-slate-950/90 text-gray-400">
      <div className="h-px w-full bg-gradient-to-r from-transparent via-indigo-500/40 to-transparent" />
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-4 py-8 sm:px-6 md:flex-row">
        <div className="text-center md:text-left">
          <h3 className="text-2xl font-bold text-white">KINGSBALFX</h3>
          <p className="text-sm text-gray-400">Forex Education | Structured Mentorship | Risk Management</p>
        </div>
        <nav className="flex flex-wrap justify-center gap-4 text-sm">
          {["About", "Privacy", "Contact", "Terms", "Policy"].map((item) => <Link key={item} href={`/${item.toLowerCase()}`} className="transition hover:text-white">{item}</Link>)}
        </nav>
        <div className="flex min-h-[36px] flex-wrap justify-center gap-3">
          {socials.map((social) => {
            const key = String(social.label || "").toLowerCase().replace(/\s+/g, "");
            const Icon = ICON_MAP[key] || FaGlobe;
            return <a key={`${social.label}-${social.url}`} href={social.url} target="_blank" rel="noopener noreferrer" title={social.label} aria-label={social.label} className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-gray-300 transition hover:-translate-y-0.5 hover:border-indigo-300/40 hover:text-white"><Icon size={18} /></a>;
          })}
        </div>
      </div>
      <div className="border-t border-gray-800 py-3 text-center text-xs">Copyright {new Date().getFullYear()} KINGSBALFX. All rights reserved.</div>
    </footer>
  );
}
