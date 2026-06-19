import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";
import FeedbackMessage from "./FeedbackMessage";

export default function PriceButton({ plan = "vip", initialPrice = null }) {
  const [price, setPrice] = useState(initialPrice);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [registrationGate, setRegistrationGate] = useState({ active: false, message: "" });
  const router = useRouter();

  useEffect(() => {
    fetch("/api/registration-gate", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setRegistrationGate({
        active: Boolean(data.active),
        message: data.message || data.gate?.message || "",
      }))
      .catch(() => {});
  }, []);

  const formatted = price
    ? new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(price)
    : null;

  const startPayment = async () => {
    setLoading(true);
    setMessage("");
    try {
      if (registrationGate.active) {
        setMessage(registrationGate.message || "Paid applications and upgrades are temporarily closed. Free registration remains open.");
        return;
      }
      if (!supabase) {
        setMessage("Payment service is not configured. Please contact support.");
        return;
      }
      const { data } = await supabase.auth.getSession();
      const user = data?.session?.user;
      if (!user) {
        const next = `/checkout?plan=${plan}`;
        router.push(`/login?next=${encodeURIComponent(next)}`);
        return;
      }
      router.push(`/checkout?plan=${encodeURIComponent(plan)}`);
    } catch (err) {
      setMessage(err.message || "Unable to open checkout.");
    } finally {
      setLoading(false);
    }
  };

  const handleShow = async () => {
    if (price) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`/api/price?plan=${plan}`);
      const data = await res.json();
      setPrice(data.price || 0);
    } catch {
      setMessage("Unable to load the price. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      {price ? (
        <>
          <div className="text-yellow-300 font-bold">Access price: {formatted}</div>
          <button
            onClick={startPayment}
            disabled={loading || registrationGate.active}
            className="px-4 py-2 bg-indigo-600 rounded text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {registrationGate.active ? "Paid Applications Closed" : loading ? "Processing..." : `Pay ${formatted}`}
          </button>
          {registrationGate.active && <div className="text-xs text-amber-200">{registrationGate.message}</div>}
        </>
      ) : (
        <button
          onClick={handleShow}
          disabled={loading}
          className="px-4 py-2 bg-yellow-400 text-black rounded font-semibold hover:bg-yellow-300 disabled:opacity-60"
        >
          {loading ? "Loading..." : "Show Price"}
        </button>
      )}
      <FeedbackMessage message={message} type="error" />
    </div>
  );
}
