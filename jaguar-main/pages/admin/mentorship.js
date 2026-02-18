import dynamic from "next/dynamic";
import { useState } from "react";
const Chat = dynamic(() => import("../../components/Chat"), { ssr: false });
export default function Mentorship() {
  const [channel, setChannel] = useState("premium");
  return (
    <div className="min-h-[calc(100vh-160px)] p-6">
      <h2 className="text-2xl font-bold">Mentorship Dashboard</h2>
      <p className="mt-2">
        Toggle between Premium and VIP community chats and view
        mentorship-specific stats.
      </p>
      <div className="mt-4 flex gap-2">
        <button onClick={() => setChannel("premium")} className="card px-3">
          Premium Community
        </button>
        <button onClick={() => setChannel("vip")} className="card px-3">
          VIP Community
        </button>
      </div>

      <div className="mt-6 grid md:grid-cols-2 gap-4">
        <div>
          <h3 className="font-semibold">
            Community Chat — {channel.toUpperCase()}
          </h3>
          <Chat channel={channel} />
        </div>
        <div>
          <h3 className="font-semibold">Mentorship Controls</h3>
          <div className="mt-2 card p-4">
            Assign mentors, create mentorship groups, view submissions
            (placeholder controls).
          </div>
        </div>
      </div>
    </div>
  );
}
