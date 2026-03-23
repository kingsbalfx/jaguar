function toYouTubeEmbed(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtu.be")) {
      const id = parsed.pathname.replace("/", "");
      return `https://www.youtube.com/embed/${id}`;
    }
    if (parsed.searchParams.get("v")) {
      return `https://www.youtube.com/embed/${parsed.searchParams.get("v")}`;
    }
    return url;
  } catch {
    return url;
  }
}

function toEmbedUrl(mediaType, mediaUrl) {
  if (!mediaUrl) return "";
  if (mediaType === "youtube") {
    return toYouTubeEmbed(mediaUrl);
  }
  return mediaUrl;
}

export default function EmbeddedLivePlayer({ mediaType, mediaUrl, title = "Live Session" }) {
  const src = toEmbedUrl(mediaType, mediaUrl);
  if (!src) return null;

  return (
    <div className="aspect-video w-full overflow-hidden rounded-lg border border-white/10">
      <iframe
        title={title}
        src={src}
        className="h-full w-full"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; camera; microphone; display-capture"
        allowFullScreen
      />
    </div>
  );
}
