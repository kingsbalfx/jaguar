// components/Header.js
import React from "react";
import Link from "next/link";

export default function Header() {
  return (
    <header className="w-full bg-transparent py-4 px-6 flex justify-between items-center">
      <div className="flex items-center gap-3">
        <img
          src="/images/jaguar.png"
          alt="Jaguar logo"
          width={150}
          height={40}
          style={{ display: "block", width: 150, height: 40 }}
        />
        <div className="text-white font-bold">KINGSBALFX</div>
      </div>
      <nav className="flex gap-3">
        <Link href="/" className="text-gray-200 hover:text-white px-3">
          Home
        </Link>

        <Link href="/pricing" className="text-gray-200 hover:text-white px-3">
          Pricing
        </Link>

        <Link href="/login" className="text-gray-200 hover:text-white px-3">
          Login
        </Link>
      </nav>
    </header>
  );
}
