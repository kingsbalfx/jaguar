// pages/login.js
import { useState } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const router = useRouter();
  const { redirectTo } = router.query; // optional original destination

  const handleLogin = async (e) => {
    e.preventDefault();
    // Authenticate with Supabase
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      alert(error.message);
    } else {
      // Redirect to callback with redirectTo param
      const to = redirectTo ? redirectTo : '';
      router.push(`/auth/callback?redirectTo=${encodeURIComponent(to)}`);
    }
  };

  return (
    <div className="card">
      <h1>Login</h1>
      <form onSubmit={handleLogin}>
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
        <button type="submit">Log In</button>
      </form>
    </div>
  );
}
