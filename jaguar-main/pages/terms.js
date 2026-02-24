// pages/terms.js
import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

const TERMS = {
  en: {
    label: "English",
    title: "Terms & Conditions",
    intro:
      'These Terms & Conditions ("Terms") govern your use of the KINGSBALFX website and services. By using our platform, you agree to abide by them.',
    sections: [
      {
        heading: "Use of Service",
        paragraphs: [
          "You must be at least 18 years old or have permission to use our services. Do not misrepresent your identity or share accounts.",
        ],
      },
      {
        heading: "Payment & Subscriptions",
        paragraphs: [
          "Access to Premium and VIP features requires payment via Korapay. Your plan remains active only after successful verification.",
        ],
      },
      {
        heading: "Refunds & Cancellations",
        paragraphs: [
          "Refunds are only considered if you have not benefited from or used the service. All refund requests must be submitted within 7 days of payment.",
        ],
        list: [
          "Refunds are only valid if the service has not been used or accessed.",
          "After 7 days, refunds are not allowed under any condition.",
          "If any usage, access, or benefit is detected, refunds will be denied.",
        ],
        footer:
          "If you believe there’s been an error, contact support with your payment reference and details.",
      },
      {
        heading: "Limitations of Liability",
        paragraphs: [
          "KINGSBALFX is not responsible for any trading losses, damages, or decisions you make using our signals, mentorship, or advice.",
        ],
      },
      {
        heading: "Changes to Terms",
        paragraphs: [
          "We may update these Terms periodically. Continued use of the website means you accept changes.",
        ],
      },
    ],
    contact: "Questions about these Terms? Email us at",
  },
  fr: {
    label: "Français",
    title: "Conditions générales",
    intro:
      "Ces Conditions générales (« Conditions ») régissent votre utilisation du site et des services KINGSBALFX. En utilisant notre plateforme, vous acceptez de les respecter.",
    sections: [
      {
        heading: "Utilisation du service",
        paragraphs: [
          "Vous devez avoir au moins 18 ans ou disposer d’une autorisation pour utiliser nos services. Ne falsifiez pas votre identité et ne partagez pas vos comptes.",
        ],
      },
      {
        heading: "Paiement et abonnements",
        paragraphs: [
          "L’accès aux fonctionnalités Premium et VIP nécessite un paiement via Korapay. Votre plan reste actif uniquement après vérification réussie.",
        ],
      },
      {
        heading: "Remboursements et annulations",
        paragraphs: [
          "Les remboursements ne sont envisagés que si vous n’avez pas bénéficié ou utilisé le service. Toute demande de remboursement doit être soumise dans les 7 jours suivant le paiement.",
        ],
        list: [
          "Les remboursements sont valables uniquement si le service n’a pas été utilisé ou consulté.",
          "Après 7 jours, aucun remboursement n’est accordé, quelle que soit la raison.",
          "Si une utilisation, un accès ou un bénéfice est constaté, le remboursement sera refusé.",
        ],
        footer:
          "Si vous pensez qu’une erreur s’est produite, contactez le support avec votre référence de paiement et les détails.",
      },
      {
        heading: "Limitation de responsabilité",
        paragraphs: [
          "KINGSBALFX n’est pas responsable des pertes de trading, dommages ou décisions que vous prenez en utilisant nos signaux, notre mentorat ou nos conseils.",
        ],
      },
      {
        heading: "Modifications des conditions",
        paragraphs: [
          "Nous pouvons mettre à jour ces Conditions périodiquement. Continuer à utiliser le site signifie que vous acceptez les changements.",
        ],
      },
    ],
    contact: "Des questions sur ces conditions ? Écrivez-nous à",
  },
};

export default function Terms() {
  const router = useRouter();
  const [lang, setLang] = useState("en");

  useEffect(() => {
    const queryLang = typeof router.query?.lang === "string" ? router.query.lang : null;
    const stored = typeof window !== "undefined" ? window.localStorage.getItem("terms_lang") : null;
    const initial = queryLang || stored || "en";
    if (TERMS[initial]) {
      setLang(initial);
    }
  }, [router.query]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("terms_lang", lang);
    }
  }, [lang]);

  const content = useMemo(() => TERMS[lang] || TERMS.en, [lang]);

  return (
    <main className="container mx-auto px-6 py-12 text-gray-800 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 className="text-3xl font-bold">{content.title}</h1>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="termsLang" className="text-gray-500">
            Language
          </label>
          <select
            id="termsLang"
            className="border border-gray-300 rounded px-2 py-1"
            value={lang}
            onChange={(e) => setLang(e.target.value)}
          >
            {Object.entries(TERMS).map(([key, item]) => (
              <option key={key} value={key}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="mb-4">{content.intro}</p>

      {content.sections.map((section) => (
        <section key={section.heading}>
          <h2 className="text-2xl font-semibold mt-6 mb-2">{section.heading}</h2>
          {section.paragraphs?.map((text, idx) => (
            <p key={idx}>{text}</p>
          ))}
          {section.list && (
            <ul className="list-disc pl-5 space-y-1 mb-3 mt-2">
              {section.list.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
          {section.footer && <p>{section.footer}</p>}
        </section>
      ))}

      <h2 className="text-2xl font-semibold mt-6 mb-2">Contact</h2>
      <p>
        {content.contact}{" "}
        <a href="mailto:shafiuabdullahi.sa3@gmail.com" className="text-indigo-600">
          shafiuabdullahi.sa3@gmail.com
        </a>
        .
      </p>
    </main>
  );
}
