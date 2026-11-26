import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Briefcase, Check, ShoppingBag, Store, UtensilsCrossed } from "lucide-react";

// Only capabilities verified in the product are listed. No channel, payment or
// automation that is not shipped is advertised here.
const SOLUTIONS = [
  {
    key: "commerce",
    icon: Store,
    title: "Commerce & boutiques",
    description: "Boutiques et commerces de proximité.",
    bullets: [
      "Répond aux questions sur vos produits",
      "Renseigne les disponibilités et les caractéristiques",
      "Transforme les échanges en demandes structurées",
    ],
    testid: "solution-commerce",
  },
  {
    key: "ecommerce",
    icon: ShoppingBag,
    title: "E-commerce",
    description: "Boutiques en ligne et catalogues produits.",
    bullets: [
      "Répond aux questions avant achat",
      "Présente les produits, conditions et informations disponibles",
      "Suit les demandes et les clients depuis le tableau de bord",
    ],
    testid: "solution-ecommerce",
  },
  {
    key: "restaurant",
    icon: UtensilsCrossed,
    title: "Restaurants & restauration",
    description: "Menus, plats et commandes.",
    bullets: [
      "Présente le catalogue et les menus",
      "Répond aux questions sur les plats et les informations disponibles",
      "Accompagne la demande de commande jusqu'à la confirmation",
    ],
    testid: "solution-restaurant",
  },
  {
    key: "services",
    icon: Briefcase,
    title: "Services & entreprises",
    description: "Entreprises de services, conseil et activités sur mesure.",
    bullets: [
      "Répond aux questions fréquentes",
      "Exploite vos documents et informations d'entreprise",
      "Oriente chaque demande vers la bonne information",
    ],
    testid: "solution-services",
  },
];

function SolutionCard({ solution, index, reduce }) {
  const Icon = solution.icon;
  const motionProps = reduce ? {} : {
    initial: { opacity: 0, y: 18 },
    whileInView: { opacity: 1, y: 0 },
    viewport: { once: true },
    transition: { duration: 0.4, delay: index * 0.05 },
  };

  return (
    <motion.article
      {...motionProps}
      className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-md sm:p-7"
      data-testid={solution.testid}>
      <Icon className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 text-primary/5" aria-hidden="true" />
      <div className="relative flex items-center gap-3">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h3 className="font-heading text-lg font-semibold">{solution.title}</h3>
          <p className="text-xs text-muted-foreground">{solution.description}</p>
        </div>
      </div>
      <ul className="relative mt-5 space-y-2.5 text-sm">
        {solution.bullets.map((bullet) => (
          <li key={bullet} className="flex items-start gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden="true" />
            {bullet}
          </li>
        ))}
      </ul>
    </motion.article>
  );
}

export default function Solutions() {
  const reduce = useReducedMotion();

  return (
    <section id="solutions" aria-labelledby="solutions-title"
      className="scroll-mt-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto py-16 lg:py-24"
      data-testid="solutions-section">
      <div className="text-center max-w-2xl mx-auto mb-14">
        <h2 id="solutions-title" className="text-2xl sm:text-3xl lg:text-4xl font-semibold tracking-tight">
          Un assistant IA adapté à votre activité
        </h2>
        <p className="mt-4 text-muted-foreground">
          Que vous vendiez des produits ou proposiez des services, votre assistant IA s'adapte
          à votre entreprise et accompagne vos clients au quotidien.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {SOLUTIONS.map((solution, index) => (
          <SolutionCard key={solution.key} solution={solution} index={index} reduce={reduce} />
        ))}
      </div>
    </section>
  );
}
