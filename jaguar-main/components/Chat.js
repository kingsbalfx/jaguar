import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);

export default function Chat({ channel = "public" }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");

  useEffect(() => {
    let mounted = true;

    async function fetchMessages() {
      const { data } = await supabase
        .from("chat_messages")
        .select("*")
        .order("created_at", { ascending: true })
        .limit(200);
      if (mounted && data) setMessages(data);
    }

    fetchMessages();

    const sub = supabase
      .channel("public:chat")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "chat_messages" },
        (payload) => {
          setMessages((prev) => [...prev, payload.new]);
        }
      )
      .subscribe();

    return () => {
      mounted = false;
      sub.unsubscribe();
    };
  }, []);

  const send = async () => {
    if (!text) return;
    await supabase.from("chat_messages").insert([{ content: text, channel }]);
    setText("");
  };

  return (
    <div className="card p-4">
      <div className="h-48 overflow-auto mb-2">
        {messages.map((m, i) => (
          <div key={i} className="mb-1">
            <strong>{m.user_email || "anon"}:</strong> {m.content}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="flex-1 p-2 rounded bg-black/20"
        />
        <button onClick={send} className="px-4 py-2 card">
          Send
        </button>
      </div>
    </div>
  );
}