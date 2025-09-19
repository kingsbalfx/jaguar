import React from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

export default function CheckoutSuccess({ success, message, reference }) {
  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-4">
          {success ? "Payment Successful" : "Payment Verification Failed"}
        </h1>
        <p className="mb-2">{message}</p>
        {reference && (
          <div className="mt-2">
            Reference: <strong>{reference}</strong>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

export async function getServerSideProps(context) {
  const reference = context.query.reference || null;
  if (!reference) {
    return {
      props: {
        success: false,
        message: "No payment reference provided.",
        reference: null,
      },
    };
  }

  // 1. Verify the transaction with Paystack (server-side)
  const paystackRes = await fetch(`https://api.paystack.co/transaction/verify/${reference}`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
    },
  });
  const paystackData = await paystackRes.json();

  // If Paystack API call failed
  if (!paystackData.status) {
    return {
      props: {
        success: false,
        message: paystackData.message || "Error verifying payment.",
        reference,
      },
    };
  }

  // 2. Check if transaction was successful
  if (paystackData.data.status !== "success") {
    return {
      props: {
        success: false,
        message: `Payment not successful (status: ${paystackData.data.status}).`,
        reference,
      },
    };
  }

  // 3. Optionally subscribe email to Mailchimp
  const email = paystackData.data.customer.email;
  if (email) {
    try {
      const listId = process.env.MAILCHIMP_LIST_ID;
      const apiKey = process.env.MAILCHIMP_API_KEY;
      const datacenter = apiKey.split("-").pop(); // e.g. 'us20'

      const subscriber = { email_address: email, status: "subscribed" };
      const mcRes = await fetch(
        `https://${datacenter}.api.mailchimp.com/3.0/lists/${listId}/members`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            // Basic Auth: 'apikey' as user and API key as password
            Authorization: `Basic ${Buffer.from(`apikey:${apiKey}`).toString("base64")}`,
          },
          body: JSON.stringify(subscriber),
        }
      );
      const mcData = await mcRes.json();
      // If already subscribed or other error, ignore
      if (mcRes.status !== 200 && mcRes.status !== 201) {
        console.warn("Mailchimp subscribe error:", mcData);
      }
    } catch (err) {
      console.error("Mailchimp API error:", err);
    }
  }

  // 4. Return success
  return {
    props: {
      success: true,
      message: "We received your payment and verified it successfully.",
      reference,
    },
  };
}
