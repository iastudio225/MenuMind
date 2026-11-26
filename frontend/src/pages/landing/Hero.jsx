import React from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight, Clock3, SlidersHorizontal, Sparkles, Wallet } from "lucide-react";
import { CHAT } from "./content";

export default function Hero() {
  const reduce = useReducedMotion();
  const fadeUp = (delay = 0) => (reduce ? {} : {
    initial: { opacity: 0, y: 16 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, delay },
  });
  const message = (index) => (reduce ? {} : {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.35, delay: 0.3 + index * 0.12 },
  });

  return (
    <section className="relative overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-secondary/40" />
        <div className="absolute -top-32 right-[-10%] h-80 w-80 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute left-[-10%] top-40 h-72 w-72 rounded-full bg-[#0F172A]/5 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-4 py-16 sm:px-6 sm:py-20 lg:grid-cols-2 lg:gap-16 lg:px-8 lg:py-28">
        <motion.div {...fadeUp(0)} className="min-w-0">
          <span className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
            <Sparkles className="h-4 w-4" aria-hidden="true" /> AI Assistant • Entreprises
          </span>

          <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight sm:text-5xl">
            Votre entreprise ne devrait plus jamais laisser un client{" "}
            <span className="text-primary">sans réponse</span>.
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Votre assistant IA répond à vos clients, connaît votre activité, traite les demandes
            et vous aide à automatiser votre quotidien. 24h/24.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/experience/rest_demo_chezawa">
              <Button size="lg" className="h-12 px-7 text-base" data-testid="hero-cta-demo">
                Tester l'assistant <ArrowRight aria-hidden="true" />
              </Button>
            </Link>
            <Link to="/register">
              <Button size="lg" variant="outline" className="h-12 px-7 text-base" data-testid="hero-cta-signup">
                Créer mon compte
              </Button>
            </Link>
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-primary" aria-hidden="true" /> Disponible 24h/24
            </span>
            <span className="flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-primary" aria-hidden="true" /> Simple à configurer
            </span>
            <span className="flex items-center gap-2">
              <Wallet className="h-4 w-4 text-primary" aria-hidden="true" /> Tarification en FCFA
            </span>
          </div>

          {/* Preserves the former hero pricing CTA (same destination, same testid). */}
          <a href="#pricing" data-testid="hero-pricing-btn"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
            Voir les tarifs <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </motion.div>

        <motion.div {...fadeUp(0.15)} className="relative min-w-0">
          <div aria-hidden="true"
            className="absolute -inset-4 rounded-[2rem] bg-gradient-to-tr from-primary/15 via-transparent to-[#0F172A]/10 blur-2xl" />

          <div className="relative overflow-hidden rounded-3xl border border-border bg-card shadow-2xl"
            data-testid="hero-chat-preview">
            <div className="flex items-center gap-3 bg-[#0F172A] px-5 py-4 text-white">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary/20 text-primary ring-1 ring-white/10">
                <Sparkles className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="truncate font-heading text-sm font-semibold">Assistant IA</p>
                <p className="flex items-center gap-1.5 text-xs text-emerald-400">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-400" /> Disponible
                </p>
              </div>
              <span className="ml-auto rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-medium text-white/70">
                Démo
              </span>
            </div>

            <div className="space-y-3 bg-[#FAF7F2] p-5">
              {CHAT.map((m, i) => (
                <motion.div key={i} {...message(i)}
                  className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] whitespace-pre-line rounded-2xl px-4 py-2.5 text-sm ${
                    m.from === "user"
                      ? "rounded-br-sm bg-primary text-primary-foreground"
                      : "rounded-bl-sm border border-border bg-white text-foreground"}`}>
                    {m.text}
                  </div>
                </motion.div>
              ))}
            </div>

            <div aria-hidden="true" className="flex items-center gap-2 border-t border-border bg-card px-4 py-3">
              <div className="min-w-0 flex-1 truncate rounded-full bg-secondary px-4 py-2 text-xs text-muted-foreground">
                Écrivez votre message…
              </div>
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground">
                <ArrowRight className="h-4 w-4" />
              </span>
            </div>
          </div>

          <p className="mt-3 text-center text-xs text-muted-foreground">
            Aperçu illustratif — conversation fictive.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
