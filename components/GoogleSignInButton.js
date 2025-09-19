// components/GoogleSignInButton.js
import { createClient } from "@supabase/supabase-js";

export default function GoogleSignInButton() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const supabase = createClient(url, key);

  const onClick = async () => {
    try {
      await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/auth/callback`
        }
      });
    } catch (err) {
      console.error("Sign-in error:", err);
      alert("Sign-in failed. See console for details.");
    }
  };

  return <button onClick={onClick} className="btn">Sign in with Google</button>;
}
