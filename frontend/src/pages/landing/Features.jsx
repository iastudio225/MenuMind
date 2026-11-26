import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { QrCode, ShieldCheck, Users } from "lucide-react";
import { FEATURES } from "./content";

const TRUST = [
  { icon: ShieldCheck, label: "Données isolées par entreprise" },
  { icon: Users, label: "Comptes et rôles pour votre équipe" },
  { icon: QrCode, label: "Widget, lien partagé et QR code" },
];

function FeatureCard({ feature, index, reduce }) {
  const Icon = feature.icon;
  const motionProps = reduce ? {} : {
    initial: { opacity: 0, y: 18 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true },
    transition: { duration: 0.4, delay: index * 0.04 },
  };
  return (
    <motion.article
      {...motionProps}
      className={`flex flex-col rounded-2xl border border-border p-6 shadow-sm transition-shadow hover:shadow-md ${
        feature.highlight ? "bg-gradient-to-br from-card to-secondary/50" : "bg-card"
      } ${feature.span}`}
      data-testid={feature.testid}>
      <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <h3 className="font-heading text-lg font-semibold">{feature.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
      {feature.chips?.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {feature.chips.map((chip) => (
            <li key={chip}
              className="rounded-full border border-border bg-secondary/60 px-2.5 py-1 text-xs text-muted-foreground">
              {chip}
            </li>
          ))}
        </ul>
      )}
    </motion.article>
  );
}

export default function Features() {
  const reduce = useReducedMotion();

  return (
    <section id="features" aria-labelledby="features-title"
      className="scroll-mt-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-16 lg:py-24"
      data-testid="features-section">
      <div className="text-center max-w-2xl mx-auto mb-14">
        <h2 id="features-title" className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">
          Bien plus qu'un simple chatbot
        </h2>
        <p className="mt-4 text-muted-foreground">
          Un assistant IA qui comprend votre activité, accompagne vos clients et vous aide à gagner du temps.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-6">
        {FEATURES.map((feature, index) => (
          <FeatureCard key={feature.key} feature={feature} index={index} reduce={reduce} />
        ))}
      </div>

      <ul className="mt-6 grid gap-4 rounded-2xl border border-border bg-card p-5 sm:grid-cols-3"
        data-testid="features-trust">
        {TRUST.map(({ icon: Icon, label }) => (
          <li key={label} className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
            {label}
          </li>
        ))}
      </ul>
    </section>
  );
}
