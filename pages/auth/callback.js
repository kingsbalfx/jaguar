// pages/auth/callback.js
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client (anon key)
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const checkRoleAndRedirect = async () => {
      // Get the current user session
      const { data, error } = await supabase.auth.getSession();
      if (error || !data.session) {
        router.push('/login'); // not logged in
        return;
      }
      const email = data.session.user.email;

      // Fetch user role from custom API (must be implemented server-side)
      try {
        const res = await fetch('/api/get-role');
        const result = await res.json();
        const role = result.role;

        // Admin check (by role or specific email)
        if (role === 'admin' || email === 'shafiuabdullahi.sa3@gmail.com') {
          router.push('/admin');
        } else if (role === 'vip') {
          router.push('/dashboard/vip');
        } else if (role === 'premium') {
          router.push('/dashboard/premium');
        } else {
          router.push('/dashboard');
        }
      } catch (err) {
        console.error('Failed to get role:', err);
        router.push('/dashboard'); // fallback
      }
    };

    checkRoleAndRedirect();
  }, [router]);

  return <p>Redirecting...</p>;
}
