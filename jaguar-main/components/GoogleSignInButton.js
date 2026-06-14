// components/GoogleSignInButton.js
import { createClient } from "@supabase/supabase-js";
import { useState } from "react";
import FeedbackMessage from "./FeedbackMessage";

export default function GoogleSignInButton() {
  const [message, setMessage] = useState("");
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const supabase = createClient(url, key);

  const onClick = async () => {
    setMessage("");
    try {
      await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`
        }
      });
    } catch (err) {
      console.error("Sign-in error:", err);
      setMessage("Google sign-in failed. Please try again.");
    }
  };

  return (
    <div className="space-y-3">
      <button onClick={onClick} className="btn">Sign in with Google</button>
      <FeedbackMessage message={message} type="error" />
    </div>
  );
}
