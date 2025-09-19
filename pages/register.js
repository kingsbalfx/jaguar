import { useEffect } from "react";
import { supabase } from "../lib/supabaseClient";
import { useRouter } from "next/router";

export default function Register() {
  const router = useRouter();
  const { plan } = router.query;

  useEffect(() => {
    // start OAuth sign-in with Google (Supabase)
    async function signIn() {
      const redirectTo = "/auth/callback";
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (error) console.error("OAuth error", error);
    }
    signIn();
  }, []);

  return (
    <div className="container mx-auto px-6 py-12 text-white">
      <h3 className="text-2xl">Redirecting to Google for sign-in...</h3>
      <p className="text-gray-300">
        After sign-in we will check the Gmail domain and redirect to payment if
        required.
      </p>
    </div>
  );
}
