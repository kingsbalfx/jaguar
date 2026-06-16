import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const TITLES = {
  error: "Action needs attention",
  success: "Update confirmed",
  warning: "Please review",
  info: "Working on it",
};

export default function FeedbackMessage({ message, type = "info", className = "" }) {
  const [visible, setVisible] = useState(Boolean(message));
  const [mounted, setMounted] = useState(false);
  const normalizedType = TITLES[type] ? type : "info";

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    setVisible(Boolean(message));
    if (!message) return undefined;
    const timer = window.setTimeout(() => setVisible(false), normalizedType === "error" ? 12000 : 7000);
    return () => window.clearTimeout(timer);
  }, [message, normalizedType]);

  if (!mounted || !message || !visible) return null;

  return createPortal(
    <div className="feedback-dock" aria-live="polite">
      <div className={`feedback-panel feedback-panel--${normalizedType} ${className}`} role={normalizedType === "error" ? "alert" : "status"}>
        <div className="feedback-panel__mark" aria-hidden="true" />
        <div className="min-w-0">
          <div className="feedback-panel__title">{TITLES[normalizedType]}</div>
          <div className="feedback-panel__message">{message}</div>
        </div>
        <button type="button" onClick={() => setVisible(false)} className="feedback-panel__close" aria-label="Dismiss notification">Dismiss</button>
      </div>
    </div>,
    document.body,
  );
}
