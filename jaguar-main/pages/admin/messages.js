// pages/admin/messages.js
import React, { useState, useEffect } from "react";

// client-side supabase instance (may be null if NEXT_PUBLIC envs missing)
import { supabase } from "../../lib/supabaseClient";

/**
 * getServerSideProps - run on the server before the page is rendered.
 * This uses the server factory to create a supabase client using the service key
 * when available. If not available, we gracefully return empty props so the build doesn't crash.
 */
import { getSupabaseClient } from "../../lib/supabaseClient";

export async function getServerSideProps(ctx) {
  const sb = getSupabaseClient({ server: true });

  if (!sb) {
    // envs missing: return empty messages so build & preview won't fail
    return { props: { initialMessages: [] } };
  }

  try {
    const { data, error } = await sb
      .from("messages")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(20);

    if (error) {
      console.error("Server fetch messages error:", error);
      return { props: { initialMessages: [] } };
    }

    return { props: { initialMessages: data || [] } };
  } catch (err) {
    console.error("Unexpected server error fetching messages:", err);
    return { props: { initialMessages: [] } };
  }
}

export default function Messages({ initialMessages = [] }) {
  const [msg, setMsg] = useState("");
  const [items, setItems] = useState(initialMessages || []);

  useEffect(() => {
    // Keep local fetch in case client-side supabase exists and we want live refresh.
    // But if supabase is null (no NEXT_PUBLIC envs), we skip client fetch.
    if (supabase) {
      fetchMessages();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchMessages() {
    if (!supabase) {
      // nothing to do on the client if public client isn't configured
      return;
    }
    const { data, error } = await supabase
      .from("messages")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(20);
    if (!error) setItems(data || []);
    else console.error("Client fetch messages error:", error);
  }

  async function saveMessage() {
    if (!supabase) {
      alert("Supabase client not configured (client). Message cannot be saved from browser.");
      return;
    }

    const { data, error } = await supabase.from("messages").insert([{ content: msg }]);
    if (!error) {
      setMsg("");
      fetchMessages();
    } else {
      alert("Unable to save message: " + (error.message || JSON.stringify(error)));
    }
  }

  return (
    <main className="container mx-auto px-6 py-8">
        <h2 className="text-2xl font-bold mb-4">Landing Page Messages</h2>

        <div className="mb-4">
          <textarea
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            className="w-full p-3 bg-gray-900 rounded"
            rows={4}
          />
          <div className="mt-2">
            <button onClick={saveMessage} className="px-4 py-2 bg-green-600 rounded">
              Save
            </button>
          </div>
        </div>

        <div>
          <h3 className="font-semibold mb-2">Recent messages</h3>
          <ul>
            {items.map((it) => (
              <li key={it.id} className="mb-2 text-gray-300">
                {it.content}
              </li>
            ))}
          </ul>
        </div>
    </main>
  );
}
