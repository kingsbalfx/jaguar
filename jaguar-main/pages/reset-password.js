import { useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
import FeedbackMessage from "../components/FeedbackMessage";

export default function ResetPassword() {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (password.length < 8 || password !== confirm) {
      setMessage("Use at least 8 characters and make sure both passwords match.");
      return;
    }
    setLoading(true);
    const client = getBrowserSupabaseClient();
    const { error } = await client.auth.updateUser({ password });
    setMessage(error ? error.message : "Password updated. You can now sign in.");
    setLoading(false);
  };

  return (
    <main className="container mx-auto max-w-md px-6 py-16 text-white">
      <form onSubmit={submit} className="glass-panel space-y-4 rounded-2xl p-6">
        <h1 className="text-2xl font-bold">Set a new password</h1>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="New password" className="w-full rounded bg-black/30 p-3" required />
        <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Confirm new password" className="w-full rounded bg-black/30 p-3" required />
        <button disabled={loading} className="w-full rounded bg-indigo-600 px-4 py-3">{loading ? "Updating..." : "Update password"}</button>
        <FeedbackMessage message={message} type={/updated/i.test(message) ? "success" : "error"} />
      </form>
    </main>
  );
}
