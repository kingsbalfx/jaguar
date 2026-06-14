import { useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

export default function Chat({ channel = "public", roomId = null }) {
  const supabase = getBrowserSupabaseClient();
  const roomKey = roomId || channel;
  const [user, setUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState(null);
  const [editing, setEditing] = useState(null);
  const [typing, setTyping] = useState([]);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);
  const channelRef = useRef(null);

  const loadMessages = async () => {
    const response = await fetch(`/api/chat/messages?roomKey=${encodeURIComponent(roomKey)}`);
    const data = await response.json();
    if (!response.ok) return setError(data.error || "Unable to load messages.");
    setMessages(data.messages || []);
    setError("");
  };

  useEffect(() => {
    if (!supabase) return undefined;
    supabase.auth.getUser().then(({ data }) => setUser(data?.user || null));
    loadMessages();
    const timer = window.setInterval(loadMessages, 3000);
    const realtime = supabase.channel(`mentorship-chat:${roomKey}`, { config: { private: true } })
      .on("broadcast", { event: "chat-refresh" }, loadMessages)
      .on("broadcast", { event: "typing" }, ({ payload }) => {
        setTyping((current) => payload.active ? [...new Set([...current, payload.name])] : current.filter((name) => name !== payload.name));
      })
      .subscribe();
    channelRef.current = realtime;
    return () => {
      window.clearInterval(timer);
      channelRef.current = null;
      supabase.removeChannel(realtime);
    };
  }, [roomKey, supabase]);

  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const notifyTyping = (active) => channelRef.current?.send({ type: "broadcast", event: "typing", payload: { name: user?.user_metadata?.full_name || user?.email || "Someone", active } });

  const send = async () => {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    setError("");
    const method = editing ? "PUT" : "POST";
    const response = await fetch("/api/chat/messages", {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ roomKey, id: editing?.id, content, replyTo: replyTo?.id || null }),
    });
    const data = await response.json();
    if (!response.ok) setError(data.error || "Unable to send message.");
    else {
      if (data.message) setMessages((current) => [...current.filter((item) => item.id !== data.message.id), data.message]);
      setText("");
      setReplyTo(null);
      setEditing(null);
      notifyTyping(false);
      await channelRef.current?.send({ type: "broadcast", event: "chat-refresh", payload: { roomKey } });
      await loadMessages();
    }
    setSending(false);
  };

  const remove = async (message) => {
    const response = await fetch("/api/chat/messages", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ roomKey, id: message.id }) });
    if (response.ok) {
      await channelRef.current?.send({ type: "broadcast", event: "chat-refresh", payload: { roomKey } });
      loadMessages();
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b141a] text-white">
      <div className="border-b border-white/10 bg-[#202c33] px-4 py-3">
        <div className="font-semibold">Mentorship Chat</div>
        <div className="text-xs text-emerald-300">{typing.length ? `${typing.join(", ")} typing...` : "Fast room messages"}</div>
      </div>
      <div className="h-[430px] space-y-2 overflow-y-auto p-3">
        {messages.map((message) => {
          const mine = message.sender_id === user?.id;
          const replied = messages.find((item) => item.id === message.reply_to);
          return (
            <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 shadow ${mine ? "bg-[#005c4b]" : "bg-[#202c33]"}`}>
                {!mine && <div className="text-xs font-semibold text-emerald-300">{message.sender_name || "Member"}</div>}
                {replied && <div className="mb-1 border-l-2 border-emerald-400 bg-black/20 px-2 py-1 text-xs">{replied.content}</div>}
                <div className="whitespace-pre-wrap break-words text-sm">{message.content}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-gray-300">
                  <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  {message.edited_at && <span>edited</span>}
                  <button onClick={() => setReplyTo(message)}>Reply</button>
                  {mine && <button onClick={() => { setEditing(message); setText(message.content); }}>Edit</button>}
                  {mine && <button onClick={() => remove(message)}>Delete</button>}
                  {mine && <span className="text-sky-300">Sent</span>}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
      {(replyTo || editing) && <div className="flex justify-between bg-[#182229] px-3 py-2 text-xs"><span>{editing ? `Editing: ${editing.content}` : `Replying to: ${replyTo.content}`}</span><button onClick={() => { setReplyTo(null); setEditing(null); setText(""); }}>Cancel</button></div>}
      {error && <div className="border-t border-red-400/20 bg-red-950/70 px-3 py-2 text-xs text-red-200">{error}</div>}
      <div className="grid grid-cols-[1fr_auto] items-end gap-2 border-t border-white/10 bg-[#202c33] p-3">
        <textarea value={text} onFocus={() => notifyTyping(true)} onBlur={() => notifyTyping(false)} onChange={(event) => { setText(event.target.value); notifyTyping(true); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} className="max-h-28 min-h-[42px] min-w-0 resize-none rounded-xl bg-[#2a3942] px-3 py-2 text-sm outline-none" placeholder="Message" />
        <button onClick={send} disabled={sending || !user} className="rounded-full bg-emerald-600 px-4 py-2 disabled:opacity-60">{sending ? "Sending..." : "Send"}</button>
      </div>
    </div>
  );
}
