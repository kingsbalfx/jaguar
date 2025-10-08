import { useState } from 'react';
import { supabase } from '../../utils/supabaseClient'; // Adjust the import path as necessary
import { useRouter } from 'next/router';

const SignUp = () => {
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const router = useRouter();

    const handleSignUp = async (e) => {
        e.preventDefault();
        const { user, error } = await supabase.auth.signUp({
            email,
            password,
            data: { full_name: fullName },
        });

        if (error) {
            setError(error.message);
            setSuccess(false);
        } else {
            setSuccess(true);
            setError(null);
            // Optionally, redirect or show a success message
        }
    };

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <form onSubmit={handleSignUp} className="bg-white p-6 rounded-lg shadow-md w-full max-w-xs">
                <h1 className="text-lg font-bold mb-4">Sign Up</h1>
                {success && <p className="text-green-500 mb-2">Check your email for confirmation!</p>}
                {error && <p className="text-red-500 mb-2">{error}</p>}
                <input
                    type="text"
                    placeholder="Full Name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    className="w-full p-2 mb-3 border rounded"
                />
                <input
                    type="email"
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full p-2 mb-3 border rounded"
                />
                <input
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="w-full p-2 mb-3 border rounded"
                />
                <button type="submit" className="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600">
                    Sign Up
                </button>
                <div className="text-center mt-4">
                    <p>
                        Already have an account?{' '}
                        <a href="/auth/login" className="text-blue-500 hover:underline">Login</a>
                    </p>
                    <p>
                        Or sign up with{' '}
                        <a href="#" className="text-blue-500 hover:underline">Google</a>
                    </p>
                </div>
            </form>
        </div>
    );
};

export default SignUp;