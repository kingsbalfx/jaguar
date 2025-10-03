// pages/contact.js
import React, { useState } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";

export default function Contact() {
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Placeholder: you should implement an API endpoint to receive messages
    console.log("Contact form submitted:", { name, email, message });
    setStatus("Message sent! We'll respond soon.");
  };

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12 text-gray-800 bg-white dark:bg-gray-900">
        <h1 className="text-3xl font-bold mb-6">Contact Us</h1>
        <p className="mb-4">
          We'd love to hear from you. Use the form below to send us a message or email us directly at 
          <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600"> shafiuabdullahi.sa3@gmail.com</a>.
        </p>

        <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
          <div>
            <label className="block mb-1 font-medium">Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full p-2 border rounded"
              required
            />
          </div>
          <div>
            <label className="block mb-1 font-medium">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full p-2 border rounded"
              required
            />
          </div>
          <div>
            <label className="block mb-1 font-medium">Message</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full p-2 border rounded"
              rows={4}
              required
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
          >
            Send Message
          </button>
        </form>

        {status && <p className="mt-4 text-green-600">{status}</p>}
      </main>
      <Footer />
    </>
  );
}
