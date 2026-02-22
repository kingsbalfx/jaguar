import { useEffect, useState } from "react";

export default function ContentLibrary() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/content/items")
      .then((res) => res.json())
      .then((data) => {
        if (data?.items) setItems(data.items);
        else setError(data?.error || "Unable to load content.");
      })
      .catch(() => setError("Unable to load content."));
  }, []);

  if (error) {
    return <div className="text-sm text-gray-400 mt-6">{error}</div>;
  }

  if (!items.length) {
    return (
      <div className="mt-6 rounded-xl border border-white/10 bg-black/30 p-4 text-gray-400">
        No content available yet.
      </div>
    );
  }

  return (
    <div className="mt-8">
      <h3 className="text-xl font-semibold mb-4">Your Resources</h3>
      <div className="grid md:grid-cols-2 gap-4">
        {items.map((item) => (
          <div key={item.id} className="rounded-xl border border-white/10 bg-black/40 p-4">
            <div className="text-sm text-gray-400">{item.segment?.toUpperCase()}</div>
            <div className="text-lg font-semibold text-white">{item.title}</div>
            {item.description && <p className="text-sm text-gray-300 mt-2">{item.description}</p>}

            {item.media_type === "text" && (
              <div className="mt-3 text-sm text-gray-200 whitespace-pre-wrap">{item.body}</div>
            )}

            {["video", "audio"].includes(item.media_type) && item.public_url && (
              <div className="mt-3">
                {item.media_type === "video" ? (
                  <video src={item.public_url} controls className="w-full rounded-lg" />
                ) : (
                  <audio src={item.public_url} controls className="w-full" />
                )}
              </div>
            )}

            {item.media_type === "pdf" && item.public_url && (
              <div className="mt-3">
                <a
                  href={item.public_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-indigo-300 underline"
                >
                  Open PDF
                </a>
              </div>
            )}

            {item.media_type === "link" && item.media_url && (
              <div className="mt-3">
                <a href={item.media_url} target="_blank" rel="noreferrer" className="text-indigo-300 underline">
                  Open Link
                </a>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
