const TITLES = {
  error: "Action required",
  success: "Completed successfully",
  warning: "Please review",
  info: "Status update",
};

export default function FeedbackMessage({ message, type = "info", className = "" }) {
  if (!message) return null;
  const normalizedType = TITLES[type] ? type : "info";

  return (
    <div className={`feedback-panel feedback-panel--${normalizedType} ${className}`} role={normalizedType === "error" ? "alert" : "status"}>
      <div className="feedback-panel__mark" aria-hidden="true" />
      <div>
        <div className="feedback-panel__title">{TITLES[normalizedType]}</div>
        <div className="feedback-panel__message">{message}</div>
      </div>
    </div>
  );
}
