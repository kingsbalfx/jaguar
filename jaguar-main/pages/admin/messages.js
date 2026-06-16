// pages/admin/messages.js
import React, { useEffect, useState } from "react";
import FeedbackMessage from "../../components/FeedbackMessage";
import { MENTORSHIP_GROUPS, getMentorshipGroupLabel } from "../../lib/mentorship-groups";

export default function Messages() {
  const [msg, setMsg] = useState("");
  const [segment, setSegment] = useState("all");
  const [items, setItems] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState({ type: "", message: "" });

  useEffect(() => {
    fetchMessages();
  }, []);

  async function fetchMessages() {
    try {
      const res = await fetch("/api/admin/messages");
      const json = await res.json();
      if (res.ok) {
        setItems(json.items || []);
      } else {
        console.error("Client fetch messages error:", json.error);
      }
    } catch (err) {
      console.error("Client fetch messages error:", err);
    }
  }

  async function saveMessage() {
    if (!msg.trim()) return;
    setLoading(true);
    setFeedback({ type: "", message: "" });
    try {
      const res = await fetch("/api/admin/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: msg, segment }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Unable to save message");
      setMsg("");
      setSegment("all");
      await fetchMessages();
      setFeedback({ type: "success", message: "Landing announcement published." });
    } catch (err) {
      setFeedback({ type: "error", message: err.message || "Unable to save message" });
    } finally {
      setLoading(false);
    }
  }

  async function updateMessage(id) {
    if (!msg.trim()) return;
    setLoading(true);
    setFeedback({ type: "", message: "" });
    try {
      const res = await fetch(`/api/admin/messages/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: msg, segment }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Unable to update message");
      setEditingId(null);
      setMsg("");
      setSegment("all");
      await fetchMessages();
      setFeedback({ type: "success", message: "Landing announcement updated." });
    } catch (err) {
      setFeedback({ type: "error", message: err.message || "Unable to update message" });
    } finally {
      setLoading(false);
    }
  }

  async function deleteMessage(id) {
    if (!confirm("Delete this message?")) return;
    try {
      const res = await fetch(`/api/admin/messages/${id}`, { method: "DELETE" });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Unable to delete message");
      await fetchMessages();
      setFeedback({ type: "success", message: "Landing announcement deleted." });
    } catch (err) {
      setFeedback({ type: "error", message: err.message || "Unable to delete message" });
    }
  }

  const startEdit = (item) => {
    setEditingId(item.id);
    setMsg(item.content || "");
    setSegment(item.segment || "all");
  };

  return (
    <main className="container mx-auto px-4 py-6 sm:px-6 sm:py-8">
      <div className="mb-5 rounded-3xl border border-indigo-300/15 bg-gradient-to-br from-indigo-600/20 via-slate-950 to-emerald-500/10 p-5 shadow-2xl">
        <div className="text-xs uppercase tracking-[0.25em] text-indigo-200">Audience Bulletin Studio</div>
        <h2 className="mt-2 text-2xl font-bold">Landing Page Announcements</h2>
        <p className="mt-2 max-w-2xl text-sm text-gray-300">Publish polished promotional updates to the landing page and route each message to the right mentorship audience.</p>
      </div>

      <div className="mb-4 space-y-3 rounded-2xl border border-white/10 bg-slate-950/70 p-4 shadow-xl">
        <textarea
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          className="w-full rounded-2xl border border-white/10 bg-black/30 p-3 text-white outline-none placeholder:text-gray-400 focus:border-indigo-300/40"
          rows={4}
          placeholder="Write a clear, professional announcement for the landing page..."
        />
        <div className="flex flex-wrap gap-3">
          <select
            className="rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
          >
            {MENTORSHIP_GROUPS.map((group) => (
              <option key={group.value} value={group.value}>{group.label}</option>
            ))}
          </select>
          {editingId ? (
            <>
              <button
                onClick={() => updateMessage(editingId)}
                className="px-4 py-2 bg-indigo-600 rounded"
                disabled={loading}
              >
              {loading ? "Saving..." : "Update Announcement"}
              </button>
              <button
                onClick={() => {
                  setEditingId(null);
                  setMsg("");
                  setSegment("all");
                }}
                className="px-4 py-2 bg-gray-700 rounded"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={saveMessage}
              className="px-4 py-2 bg-green-600 rounded"
              disabled={loading}
            >
              {loading ? "Saving..." : "Publish Announcement"}
            </button>
          )}
        </div>
        <FeedbackMessage message={feedback.message} type={feedback.type || "info"} />
      </div>

      <div>
        <h3 className="font-semibold mb-2">Recent announcements</h3>
        <ul>
          {items.map((it) => (
            <li key={it.id} className="mb-3 rounded border border-white/10 bg-black/30 p-3 text-gray-300">
              <div className="text-sm moving-italic">
                <span>{it.content}</span>
              </div>
              <div className="mt-1 text-xs text-gray-500 flex flex-wrap gap-3">
                <span>Audience: {getMentorshipGroupLabel(it.segment || "all")}</span>
                {it.author && (
                  <span>
                    By {it.author.name || it.author.username || it.author.email || "Admin"}
                  </span>
                )}
                {it.created_at && <span>{new Date(it.created_at).toLocaleString()}</span>}
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => startEdit(it)}
                  className="px-3 py-1 rounded bg-indigo-600 text-xs"
                >
                  Edit
                </button>
                <button
                  onClick={() => deleteMessage(it.id)}
                  className="px-3 py-1 rounded bg-red-600 text-xs"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
