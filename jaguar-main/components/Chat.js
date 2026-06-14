import { useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
import FeedbackMessage from "./FeedbackMessage";

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
  const [showNewMessages, setShowNewMessages] = useState(false);
  const messagesRef = useRef(null);
  const channelRef = useRef(null);
  const stickToBottomRef = useRef(true);
  const previousMessageCountRef = useRef(0);
  const loadingRef = useRef(false);
  const typingTimerRef = useRef(null);
  const typingExpiryRef = useRef(new Map());
  const lastTypingBroadcastRef = useRef(0);

  const loadMessages = async () => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const response = await fetch(`/api/chat/messages?roomKey=${encodeURIComponent(roomKey)}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) return setError(data.error || "Unable to load messages.");
      setMessages(data.messages || []);
      setError("");
    } finally {
      loadingRef.current = false;
    }
  };

  useEffect(() => {
    if (!supabase) return undefined;
    supabase.auth.getUser().then(({ data }) => setUser(data?.user || null));
    loadMessages();
    const timer = window.setInterval(loadMessages, 30000);
    const realtime = supabase.channel(`mentorship-chat:${roomKey}`, { config: { private: true } })
      .on("broadcast", { event: "chat-refresh" }, loadMessages)
      .on("broadcast", { event: "typing" }, ({ payload }) => {
        const name = payload?.name;
        if (!name) return;
        window.clearTimeout(typingExpiryRef.current.get(name));
        if (!payload.active) {
          typingExpiryRef.current.delete(name);
          setTyping((current) => current.filter((item) => item !== name));
          return;
        }
        setTyping((current) => [...new Set([...current, name])]);
        typingExpiryRef.current.set(name, window.setTimeout(() => {
          typingExpiryRef.current.delete(name);
          setTyping((current) => current.filter((item) => item !== name));
        }, 3500));
      })
      .on("postgres_changes", { event: "*", schema: "public", table: "mentorship_messages", filter: `room_key=eq.${roomKey}` }, ({ eventType, new: next }) => {
        if (!next?.id) return;
        setMessages((current) => {
          if (eventType === "UPDATE" && next.deleted_at) return current.filter((item) => item.id !== next.id);
          const withoutCurrent = current.filter((item) => item.id !== next.id);
          return [...withoutCurrent, next].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        });
      })
      .subscribe();
    channelRef.current = realtime;
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") loadMessages();
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(typingTimerRef.current);
      typingExpiryRef.current.forEach((timeout) => window.clearTimeout(timeout));
      typingExpiryRef.current.clear();
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      channelRef.current = null;
      supabase.removeChannel(realtime);
    };
  }, [roomKey, supabase]);

  useEffect(() => {
    const container = messagesRef.current;
    if (!container) return;
    const hasNewMessage = messages.length > previousMessageCountRef.current;
    previousMessageCountRef.current = messages.length;
    if (stickToBottomRef.current) {
      container.scrollTo({ top: container.scrollHeight, behavior: hasNewMessage ? "smooth" : "auto" });
      setShowNewMessages(false);
    } else if (hasNewMessage) {
      setShowNewMessages(true);
    }
  }, [messages]);

  const notifyTyping = (active) => {
    const name = user?.user_metadata?.full_name || user?.email || "Someone";
    window.clearTimeout(typingTimerRef.current);
    const now = Date.now();
    if (!active || now - lastTypingBroadcastRef.current > 1500) {
      lastTypingBroadcastRef.current = now;
      channelRef.current?.send({ type: "broadcast", event: "typing", payload: { name, active } });
    }
    if (active) {
      typingTimerRef.current = window.setTimeout(() => {
        channelRef.current?.send({ type: "broadcast", event: "typing", payload: { name, active: false } });
      }, 2500);
    }
  };

  const scrollChatToBottom = () => {
    const container = messagesRef.current;
    if (!container) return;
    stickToBottomRef.current = true;
    setShowNewMessages(false);
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  };

  const handleMessageScroll = () => {
    const container = messagesRef.current;
    if (!container) return;
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    stickToBottomRef.current = nearBottom;
    if (nearBottom) setShowNewMessages(false);
  };

  const send = async () => {
    const content = text.trim();
    if (!content || sending) return;
    setSending(true);
    setError("");
    try {
      const method = editing ? "PUT" : "POST";
      const response = await fetch("/api/chat/messages", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roomKey, id: editing?.id, content, replyTo: replyTo?.id || null }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Unable to send message.");
        return;
      }
      stickToBottomRef.current = true;
      if (data.message) {
        setMessages((current) => [...current.filter((item) => item.id !== data.message.id), data.message].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)));
      }
      setText("");
      setReplyTo(null);
      setEditing(null);
      notifyTyping(false);
      channelRef.current?.send({ type: "broadcast", event: "chat-refresh", payload: { roomKey } });
    } catch {
      setError("Unable to send message. Check your connection and try again.");
    } finally {
      setSending(false);
    }
  };

  const remove = async (message) => {
    setError("");
    try {
      const response = await fetch("/api/chat/messages", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ roomKey, id: message.id }) });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || "Unable to delete message.");
        return;
      }
      setMessages((current) => current.filter((item) => item.id !== message.id));
      channelRef.current?.send({ type: "broadcast", event: "chat-refresh", payload: { roomKey } });
    } catch {
      setError("Unable to delete message. Check your connection and try again.");
    }
  };

  return (
    <div className="overflow-hidden rounded-3xl border border-white/10 bg-[#0b141a] text-white shadow-2xl">
      <div className="flex items-center gap-3 border-b border-white/10 bg-[#202c33] px-4 py-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-700 text-sm font-bold text-white shadow-lg">
          MC
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-semibold">Mentorship Community</div>
          <div className="truncate text-xs text-emerald-300">{typing.length ? `${typing.join(", ")} typing...` : `${messages.length} room messages`}</div>
        </div>
        <div className="rounded-full bg-white/5 px-3 py-1.5 text-[11px] text-gray-300">Live chat</div>
      </div>
      <div className="relative">
      <div
        ref={messagesRef}
        onScroll={handleMessageScroll}
        className="h-[min(62vh,560px)] min-h-[390px] space-y-2 overflow-y-auto bg-[#0b141a] p-3 sm:p-5"
        style={{ backgroundImage: "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.035) 0 1px, transparent 1.5px)", backgroundSize: "18px 18px" }}
      >
        {!messages.length && (
          <div className="mx-auto mt-12 max-w-sm rounded-xl bg-[#182229]/95 px-4 py-3 text-center text-sm text-gray-300 shadow">
            No messages yet. Start the mentorship conversation.
          </div>
        )}
        {messages.map((message) => {
          const mine = message.sender_id === user?.id;
          const replied = messages.find((item) => item.id === message.reply_to);
          return (
            <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`group max-w-[88%] rounded-xl px-3 py-2 shadow-md sm:max-w-[72%] ${mine ? "rounded-tr-sm bg-[#005c4b]" : "rounded-tl-sm bg-[#202c33]"}`}>
                {!mine && <div className="text-xs font-semibold text-emerald-300">{message.sender_name || "Member"}</div>}
                {replied && <div className="mb-1.5 max-h-20 overflow-hidden rounded border-l-4 border-emerald-400 bg-black/20 px-2 py-1.5 text-xs text-gray-200">{replied.content}</div>}
                <div className="whitespace-pre-wrap break-words pr-2 text-sm leading-relaxed">{message.content}</div>
                <div className="mt-1 flex flex-wrap items-center justify-end gap-2 text-[10px] text-gray-300">
                  {message.edited_at && <span>edited</span>}
                  <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  {mine && <span className="font-semibold text-sky-300">Sent</span>}
                </div>
                <div className="mt-1 flex flex-wrap justify-end gap-3 border-t border-white/5 pt-1 text-[10px] text-gray-300 opacity-80 sm:opacity-0 sm:transition sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
                  <button type="button" onClick={() => setReplyTo(message)} className="hover:text-white">Reply</button>
                  {mine && <button type="button" onClick={() => { setEditing(message); setText(message.content); }} className="hover:text-white">Edit</button>}
                  {mine && <button type="button" onClick={() => remove(message)} className="hover:text-red-300">Delete</button>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {showNewMessages && (
        <button type="button" onClick={scrollChatToBottom} className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-xl">
          New messages
        </button>
      )}
      </div>
      {(replyTo || editing) && <div className="flex justify-between bg-[#182229] px-3 py-2 text-xs"><span>{editing ? `Editing: ${editing.content}` : `Replying to: ${replyTo.content}`}</span><button onClick={() => { setReplyTo(null); setEditing(null); setText(""); }}>Cancel</button></div>}
      <FeedbackMessage message={error} type="error" />
      <div className="grid grid-cols-[1fr_auto] items-end gap-2 border-t border-white/10 bg-[#202c33] p-3">
        <textarea value={text} onFocus={() => notifyTyping(true)} onBlur={() => notifyTyping(false)} onChange={(event) => { setText(event.target.value); notifyTyping(true); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} className="max-h-28 min-h-[46px] min-w-0 resize-none rounded-3xl bg-[#2a3942] px-4 py-3 text-sm outline-none placeholder:text-gray-400 focus:ring-1 focus:ring-emerald-500/60" placeholder="Type a message" />
        <button type="button" onClick={send} disabled={sending || !user || !text.trim()} aria-label="Send message" className="grid h-12 w-12 place-items-center rounded-full bg-emerald-600 text-sm font-bold shadow-lg transition hover:bg-emerald-500 disabled:opacity-40">
          {sending ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
