import { useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

export default function Chat({ channel = "public", roomId = null }) {
  const supabase = getBrowserSupabaseClient();
  const [user, setUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [replyTo, setReplyTo] = useState(null);
  const [editing, setEditing] = useState(null);
  const [typing, setTyping] = useState([]);
  const [readCounts, setReadCounts] = useState({});
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const bottomRef = useRef(null);
  const channelRef = useRef(null);

  const roomKey = roomId || channel;
  const loadMessages = async () => {
    if (!supabase) return;
    const activeUser = user || (await supabase.auth.getUser()).data?.user || null;
    const [{ data }, { data: reads }, { data: reactions }] = await Promise.all([
      supabase.from("mentorship_messages").select("*").eq("room_key", roomKey).is("deleted_at", null).order("created_at").limit(300),
      supabase.from("mentorship_message_reads").select("message_id,user_id").eq("room_key", roomKey),
      supabase.from("mentorship_message_reactions").select("message_id,user_id,emoji"),
    ]);
    const reactionMap = (reactions || []).reduce((map, reaction) => {
      const current = map[reaction.message_id] || {};
      current[reaction.emoji] = [...(current[reaction.emoji] || []), reaction.user_id];
      return { ...map, [reaction.message_id]: current };
    }, {});
    const enriched = await Promise.all((data || []).map(async (message) => {
      if (!message.attachment_url) return { ...message, reactions: reactionMap[message.id] || {} };
      const { data: signed } = await supabase.storage.from("mentorship-chat").createSignedUrl(message.attachment_url, 3600);
      return { ...message, reactions: reactionMap[message.id] || {}, attachment_signed_url: signed?.signedUrl || "" };
    }));
    setMessages(enriched);
    setReadCounts((reads || []).reduce((counts, receipt) => ({ ...counts, [receipt.message_id]: (counts[receipt.message_id] || 0) + 1 }), {}));
    const unread = (data || []).filter((message) => message.sender_id !== activeUser?.id).map((message) => ({ room_key: roomKey, message_id: message.id, user_id: activeUser?.id })).filter((receipt) => receipt.user_id);
    if (unread.length) await supabase.from("mentorship_message_reads").upsert(unread, { onConflict: "message_id,user_id" });
  };

  useEffect(() => {
    if (!supabase) return undefined;
    let realtime;
    supabase.auth.getUser().then(({ data }) => setUser(data?.user || null));
    loadMessages();
    realtime = supabase
      .channel(`mentorship-chat:${roomKey}`, { config: { private: true, presence: { key: `typing-${Math.random()}` } } })
      .on("postgres_changes", { event: "*", schema: "public", table: "mentorship_messages", filter: `room_key=eq.${roomKey}` }, loadMessages)
      .on("postgres_changes", { event: "*", schema: "public", table: "mentorship_message_reactions" }, loadMessages)
      .on("postgres_changes", { event: "*", schema: "public", table: "mentorship_message_reads", filter: `room_key=eq.${roomKey}` }, loadMessages)
      .on("broadcast", { event: "typing" }, ({ payload }) => {
        setTyping((current) => payload.active ? [...new Set([...current, payload.name])] : current.filter((name) => name !== payload.name));
      })
      .subscribe();
    channelRef.current = realtime;
    return () => {
      channelRef.current = null;
      supabase.removeChannel(realtime);
    };
  }, [roomKey, supabase]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const notifyTyping = async (active) => {
    const name = user?.email || "Someone";
    await channelRef.current?.send({ type: "broadcast", event: "typing", payload: { name, active } });
  };

  const send = async () => {
    const content = text.trim();
    if (!content || !supabase || !user) return;
    if (editing) {
      await supabase.from("mentorship_messages").update({ content, edited_at: new Date().toISOString() }).eq("id", editing.id).eq("sender_id", user.id);
    } else {
      await supabase.from("mentorship_messages").insert({ room_key: roomKey, sender_id: user.id, sender_name: user.email, content, reply_to: replyTo?.id || null });
    }
    setText("");
    setReplyTo(null);
    setEditing(null);
    notifyTyping(false);
  };

  const remove = async (message) => {
    await supabase.from("mentorship_messages").update({ deleted_at: new Date().toISOString() }).eq("id", message.id);
  };

  const react = async (message, emoji) => {
    await supabase.rpc("toggle_mentorship_reaction", { requested_message: message.id, requested_emoji: emoji });
  };

  const upload = async (event) => {
    const file = event.target.files?.[0];
    if (!file || !user) return;
    setUploading(true);
    const path = `${roomKey}/${user.id}/${Date.now()}-${file.name.replace(/[^a-zA-Z0-9._-]/g, "_")}`;
    const { error } = await supabase.storage.from("mentorship-chat").upload(path, file);
    if (!error) {
      await supabase.from("mentorship_messages").insert({ room_key: roomKey, sender_id: user.id, sender_name: user.email, content: file.name, attachment_url: path, attachment_type: file.type });
    }
    setUploading(false);
    event.target.value = "";
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b141a] text-white">
      <div className="border-b border-white/10 bg-[#202c33] px-4 py-3">
        <div className="font-semibold">{channel.toUpperCase()} Mentorship Chat</div>
        <div className="text-xs text-emerald-300">{typing.length ? `${typing.join(", ")} typing...` : "Supabase realtime"}</div>
      </div>
      <div className="h-[430px] space-y-2 overflow-y-auto bg-[#0b141a] p-3">
        {messages.map((message) => {
          const mine = message.sender_id === user?.id;
          const replied = messages.find((item) => item.id === message.reply_to);
          return (
            <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-xl px-3 py-2 shadow ${mine ? "bg-[#005c4b]" : "bg-[#202c33]"}`}>
                {!mine && <div className="text-xs font-semibold text-emerald-300">{message.sender_name || "Member"}</div>}
                {replied && <div className="mb-1 border-l-2 border-emerald-400 bg-black/20 px-2 py-1 text-xs opacity-80">{replied.content}</div>}
                {message.attachment_url && <a className="block break-all text-sm text-sky-300 underline" href={message.attachment_signed_url || "#"} target="_blank" rel="noreferrer">{message.content}</a>}
                {!message.attachment_url && <div className="whitespace-pre-wrap break-words text-sm">{message.content}</div>}
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-gray-300">
                  <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  {message.edited_at && <span>edited</span>}
                  <button onClick={() => setReplyTo(message)}>Reply</button>
                  {mine && <button onClick={() => { setEditing(message); setText(message.content); }}>Edit</button>}
                  {mine && <button onClick={() => remove(message)}>Delete</button>}
                  {mine && <span className="text-sky-300">✓✓ {readCounts[message.id] || 0}</span>}
                </div>
                <div className="mt-1 flex gap-1">
                  {["👍", "❤️", "🔥"].map((emoji) => <button key={emoji} onClick={() => react(message, emoji)} className="rounded bg-black/20 px-1 text-xs">{emoji}{message.reactions?.[emoji]?.length || ""}</button>)}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
      {(replyTo || editing) && <div className="flex justify-between bg-[#182229] px-3 py-2 text-xs"><span>{editing ? `Editing: ${editing.content}` : `Replying to: ${replyTo.content}`}</span><button onClick={() => { setReplyTo(null); setEditing(null); setText(""); }}>Cancel</button></div>}
      <div className="flex items-end gap-2 border-t border-white/10 bg-[#202c33] p-3">
        <input ref={fileRef} type="file" className="hidden" onChange={upload} />
        <button disabled={uploading} onClick={() => fileRef.current?.click()} className="rounded-full bg-white/10 px-3 py-2">{uploading ? "..." : "Attach"}</button>
        <textarea value={text} onFocus={() => notifyTyping(true)} onBlur={() => notifyTyping(false)} onChange={(event) => { setText(event.target.value); notifyTyping(true); }} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} className="max-h-28 min-h-[42px] flex-1 resize-none rounded-xl bg-[#2a3942] px-3 py-2 text-sm outline-none" placeholder="Message" />
        <button onClick={send} className="rounded-full bg-emerald-600 px-4 py-2">Send</button>
      </div>
    </div>
  );
}
