const SOCIAL_DEFINITIONS = [
  { label: "Instagram", keys: ["NEXT_PUBLIC_SOCIAL_INSTAGRAM", "NEXT_PUBLIC_INSTAGRAM_URL", "SOCIAL_INSTAGRAM", "INSTAGRAM_URL", "INSTAGRAM"] },
  { label: "X", keys: ["NEXT_PUBLIC_SOCIAL_X", "NEXT_PUBLIC_SOCIAL_TWITTER", "NEXT_PUBLIC_X_URL", "NEXT_PUBLIC_TWITTER_URL", "SOCIAL_X", "SOCIAL_TWITTER", "X_URL", "TWITTER_URL", "X", "TWITTER"] },
  { label: "LinkedIn", keys: ["NEXT_PUBLIC_SOCIAL_LINKEDIN", "NEXT_PUBLIC_LINKEDIN_URL", "SOCIAL_LINKEDIN", "LINKEDIN_URL", "LINKEDIN"] },
  { label: "YouTube", keys: ["NEXT_PUBLIC_SOCIAL_YOUTUBE", "NEXT_PUBLIC_YOUTUBE_URL", "SOCIAL_YOUTUBE", "YOUTUBE_URL", "YOUTUBE"] },
  { label: "Telegram", keys: ["NEXT_PUBLIC_SOCIAL_TELEGRAM", "NEXT_PUBLIC_TELEGRAM_URL", "SOCIAL_TELEGRAM", "TELEGRAM_URL", "TELEGRAM"] },
  { label: "Snapchat", keys: ["NEXT_PUBLIC_SOCIAL_SNAPCHAT", "NEXT_PUBLIC_SNAPCHAT_URL", "SOCIAL_SNAPCHAT", "SNAPCHAT_URL", "SNAPCHAT"] },
  { label: "TikTok", keys: ["NEXT_PUBLIC_SOCIAL_TIKTOK", "NEXT_PUBLIC_TIKTOK_URL", "SOCIAL_TIKTOK", "TIKTOK_URL", "TIKTOK"] },
  { label: "WhatsApp", keys: ["NEXT_PUBLIC_SOCIAL_WHATSAPP", "NEXT_PUBLIC_WHATSAPP_URL", "SOCIAL_WHATSAPP", "WHATSAPP_URL", "WHATSAPP"] },
  { label: "Facebook", keys: ["NEXT_PUBLIC_SOCIAL_FACEBOOK", "NEXT_PUBLIC_FACEBOOK_URL", "SOCIAL_FACEBOOK", "FACEBOOK_URL", "FACEBOOK"] },
  { label: "Website", keys: ["NEXT_PUBLIC_SOCIAL_WEBSITE", "NEXT_PUBLIC_WEBSITE_URL", "SOCIAL_WEBSITE", "WEBSITE_URL", "WEBSITE"] },
];

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
    if (platform.includes("snapchat")) return `https://snapchat.com/add/${handle}`;
    if (platform.includes("tiktok")) return `https://tiktok.com/@${handle}`;
  }
  return `https://${raw.replace(/^\/+/, "")}`;
}

function firstConfigured(keys) {
  for (const key of keys) {
    const value = process.env[key];
    if (String(value || "").trim()) return value;
  }
  return "";
}

function parseSocials(raw = "") {
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === "object") {
      return Object.entries(parsed).map(([label, url]) => ({ label, url }));
    }
  } catch {
    return raw.split(",").map((item) => item.trim()).filter(Boolean).map((pair) => {
      const separator = pair.includes("|") ? "|" : ":";
      const separatorIndex = pair.indexOf(separator);
      return {
        label: separatorIndex >= 0 ? pair.slice(0, separatorIndex).trim() : "Website",
        url: separatorIndex >= 0 ? pair.slice(separatorIndex + 1).trim() : pair,
      };
    });
  }
  return [];
}

export default function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const parsed = parseSocials(process.env.NEXT_PUBLIC_SOCIALS || process.env.SOCIALS || "");
  const parsedByLabel = new Map(parsed.map((item) => [String(item.label || "").toLowerCase(), item.url || item.value]));
  const socials = SOCIAL_DEFINITIONS.map((definition) => {
    const labelKey = definition.label.toLowerCase();
    const raw =
      parsedByLabel.get(labelKey) ||
      (definition.label === "X" ? parsedByLabel.get("twitter") : "") ||
      firstConfigured(definition.keys);
    return {
      label: definition.label,
      url: normalizeSocialUrl(raw, definition.label),
    };
  });

  res.setHeader("Cache-Control", "no-store");
  return res.status(200).json({ socials });
}
