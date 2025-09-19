import React from "react";

export default function Footer() {
  // Social links expected in NEXT_PUBLIC_SOCIALS as a JSON string or comma-separated list of label|url
  const raw = process.env.NEXT_PUBLIC_SOCIALS || "";
  let socials = [];
  try {
    socials = JSON.parse(raw);
  } catch (e) {
    if (raw) {
      socials = raw.split(",").map((s) => {
        const [label, url] = s.split("|");
        return { label: label?.trim(), url: url?.trim() };
      });
    }
  }

  return (
    <footer className="w-full py-6 bg-black text-white mt-12">
      <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-center">
        <div>
          <div className="font-bold text-lg">KINGSBALFX</div>
          <div className="text-sm text-gray-300">
            Forex mentorship • Signals • VIP challenges
          </div>
        </div>
        <div className="mt-4 md:mt-0">
          {socials.length ? (
            <div className="flex gap-4">
              {socials.map((s, i) => (
                <a
                  key={i}
                  href={s.url}
                  className="text-gray-200 hover:underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  {s.label}
                </a>
              ))}
            </div>
          ) : (
            <div className="text-gray-400">
              No social links configured. Set NEXT_PUBLIC_SOCIALS in .env
            </div>
          )}
        </div>
      </div>
    </footer>
  );
}
