// pages/register.js
import { useState } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const router = useRouter();

  // Handle email/password sign-up
  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) {
      alert(error.message);
    } else {
      // On successful sign-up, go to callback
      router.push('/auth/callback');
    }
  };

  // Handle Google OAuth sign-in
  const handleGoogleSignIn = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        // Redirect back to auth callback page after Google login
        redirectTo: `${window.location.origin}/auth/callback`
      }
    });
    if (error) alert(error.message);
    // No manual redirect needed – Supabase will navigate to the callback URL
  };

  return (
    <div className="card">
      <h1>Register</h1>
      <form onSubmit={handleEmailSignUp}>
        <label>
          Email:
          <input 
            type="email" 
            value={email}
            onChange={(e) => setEmail(e.target.value)} 
            required 
          />
        </label>
        <br />
        <label>
          Password:
          <input 
            type="password" 
            value={password}
            onChange={(e) => setPassword(e.target.value)} 
            required 
          />
        </label>
        <br />
        <button type="submit">Sign Up</button>
      </form>
      <hr />
      <button onClick={handleGoogleSignIn}>
        Continue with Google
      </button>
    </div>
  );
}
