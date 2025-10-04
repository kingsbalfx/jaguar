// pages/contact.js
import React, { useState } from "react";

export default function Contact() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: connect to server inbox or email
    setStatus("Your message has been sent. We will reply soon.");
  };

  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
      <h1 className="text-3xl font-bold mb-6">Contact Us</h1>
      <p className="mb-4">
        Email: <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">shafiuabdullahi.sa3@gmail.com</a>
      </p>

      <form onSubmit={handleSubmit} className="max-w-md space-y-4">
        <div>
          <label className="block mb-1 font-medium">Name</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full p-2 border rounded" required />
        </div>
        <div>
          <label className="block mb-1 font-medium">Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full p-2 border rounded" required />
        </div>
        <div>
          <label className="block mb-1 font-medium">Message</label>
          <textarea value={message} onChange={e => setMessage(e.target.value)} className="w-full p-2 border rounded" rows={4} required />
        </div>
        <button type="submit" className="px-4 py-2 bg-indigo-600 text-white rounded">Send</button>
      </form>

      {status && <p className="mt-4 text-green-600">{status}</p>}
    </main>
  );
}
