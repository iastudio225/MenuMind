import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";

export default function FinalCta() {
  return (
    <section className="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto pb-24" data-testid="final-cta-section">
      <div className="relative overflow-hidden rounded-3xl bg-foreground px-6 py-14 text-center text-white shadow-2xl sm:px-10 sm:py-16 lg:py-20">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-primary/30 blur-3xl" />
          <div className="absolute -bottom-28 -left-20 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />
        </div>

        <div className="relative">
          <span className="mx-auto mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-white/10 text-primary ring-1 ring-white/10">
            <Sparkles className="h-6 w-6" aria-hidden="true" />
          </span>

          <h2 className="mx-auto max-w-2xl text-2xl font-semibold tracking-tight sm:text-3xl lg:text-4xl">
            Et si votre entreprise avait un assistant qui ne s'arrête jamais ?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-white/70">
            Configurez votre assistant IA, donnez-lui les informations de votre entreprise
            et laissez-le accompagner vos clients au quotidien.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link to="/register" className="w-full sm:w-auto">
              <Button size="lg" className="h-12 w-full bg-primary-ink px-7 text-base hover:bg-primary-ink/90 sm:w-auto"
                data-testid="cta-bottom-signup">
                Créer mon assistant IA <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </Link>
            <Link to="/experience/rest_demo_chezawa" className="w-full sm:w-auto">
              <Button size="lg" variant="outline"
                className="h-12 w-full border-white/20 bg-white/5 px-7 text-base text-white hover:bg-white/10 hover:text-white sm:w-auto"
                data-testid="cta-bottom-demo">
                Découvrir la démo
              </Button>
            </Link>
          </div>

          <p className="mt-6 text-xs text-white/60">
            Sans carte bancaire · mise en route en quelques étapes.
          </p>
        </div>
      </div>
    </section>
  );
}
