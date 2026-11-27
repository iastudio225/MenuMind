import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import api from "@/lib/api";
import { formatFCFA } from "@/lib/format";
import { PLAN_INCLUDES, STATIC_PLANS } from "./content";

export default function Pricing() {
  const [plans, setPlans] = useState(STATIC_PLANS);

  useEffect(() => {
    api.get("/plans").then(({ data }) => {
      if (Array.isArray(data) && data.length) {
        const merged = STATIC_PLANS.map((sp) => {
          const found = data.find((d) => d.code === sp.code);
          return found ? { ...sp, price: found.price } : sp;
        });
        setPlans(merged);
      }
    }).catch(() => {});
  }, []);

  return (
    <section id="pricing" aria-labelledby="pricing-title"
      className="scroll-mt-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-16 lg:py-24"
      data-testid="pricing-section">
      <div className="text-center max-w-2xl mx-auto mb-10">
        <h2 id="pricing-title" className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">
          Des offres adaptées à la croissance de votre entreprise
        </h2>
        <p className="mt-4 text-muted-foreground">
          Choisissez l'offre qui correspond à vos besoins. Évoluez à votre rythme.
        </p>
      </div>

      <div className="mx-auto mb-10 max-w-5xl rounded-2xl border border-border bg-card p-5"
        data-testid="pricing-includes">
        <p className="text-sm font-semibold">Inclus dans toutes les offres</p>
        <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {PLAN_INCLUDES.map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-muted-foreground">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
        {plans.map((p) => (
          <div key={p.code}
            className={`relative flex flex-col rounded-2xl border p-7 sm:p-8 transition-shadow ${
              p.highlighted
                ? "border-primary bg-card shadow-xl md:-translate-y-3"
                : "border-border bg-card shadow-sm"}`}
            data-testid={`pricing-card-${p.code.toLowerCase()}`}>
            {p.badge && (
              <span className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-xs font-semibold ${
                p.highlighted ? "bg-primary-ink text-white" : "bg-secondary text-secondary-foreground"}`}>
                {p.badge}
              </span>
            )}
            <h3 className="font-heading text-lg font-bold">{p.code}</h3>
            <p className="mt-1 min-h-[2.5rem] text-sm text-muted-foreground">{p.desc}</p>
            <div className="mt-6">
              <span className="text-3xl font-bold font-heading">{formatFCFA(p.price)}</span>
              <span className="text-muted-foreground text-sm"> /mois</span>
            </div>
            <div className="flex-1" />
            <Link to="/register" className="mt-8 block">
              <Button className={`w-full ${p.highlighted ? "bg-primary-ink hover:bg-primary-ink/90" : ""}`}
                variant={p.highlighted ? "default" : "outline"}
                data-testid={`pricing-plan-${p.code.toLowerCase()}-btn`}>
                Choisir {p.code}
              </Button>
            </Link>
          </div>
        ))}
      </div>

      <p className="mt-8 text-center text-xs text-muted-foreground">
        Tarifs mensuels en FCFA.
      </p>
    </section>
  );
}
