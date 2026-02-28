// pages/admin/messages.js
import React, { useEffect, useState } from "react";

export default function Messages() {
  const [msg, setMsg] = useState("");
  const [segment, setSegment] = useState("all");
  const [items, setItems] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(false);

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
    } catch (err) {
      alert(err.message || "Unable to save message");
    } finally {
      setLoading(false);
    }
  }

  async function updateMessage(id) {
    if (!msg.trim()) return;
    setLoading(true);
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
    } catch (err) {
      alert(err.message || "Unable to update message");
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
    } catch (err) {
      alert(err.message || "Unable to delete message");
    }
  }

  const startEdit = (item) => {
    setEditingId(item.id);
    setMsg(item.content || "");
    setSegment(item.segment || "all");
  };

  return (
    <main className="container mx-auto px-6 py-8">
      <h2 className="text-2xl font-bold mb-4">Landing Page Messages</h2>

      <div className="mb-4 space-y-3">
        <textarea
          value={msg}
          onChange={(e) => setMsg(e.target.value)}
          className="w-full p-3 bg-gray-900 rounded"
          rows={4}
          placeholder="Write a message for the landing page..."
        />
        <div className="flex flex-wrap gap-3">
          <select
            className="rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
          >
            <option value="all">All</option>
            <option value="free">Free</option>
            <option value="premium">Premium</option>
            <option value="vip">VIP</option>
            <option value="pro">Pro</option>
            <option value="lifetime">Lifetime</option>
          </select>
          {editingId ? (
            <>
              <button
                onClick={() => updateMessage(editingId)}
                className="px-4 py-2 bg-indigo-600 rounded"
                disabled={loading}
              >
                {loading ? "Saving..." : "Update Message"}
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
              {loading ? "Saving..." : "Save Message"}
            </button>
          )}
        </div>
      </div>

      <div>
        <h3 className="font-semibold mb-2">Recent messages</h3>
        <ul>
          {items.map((it) => (
            <li key={it.id} className="mb-3 rounded border border-white/10 bg-black/30 p-3 text-gray-300">
              <div className="text-sm moving-italic">
                <span>{it.content}</span>
              </div>
              <div className="mt-1 text-xs text-gray-500 flex flex-wrap gap-3">
                <span>Segment: {it.segment || "all"}</span>
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
