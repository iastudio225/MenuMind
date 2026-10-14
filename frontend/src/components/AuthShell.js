import React from "react";
import { Link } from "react-router-dom";
import { Bot } from "lucide-react";

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Left brand panel */}
      <div className="hidden lg:flex flex-col justify-between bg-[#0F172A] text-white p-12 relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-80 h-80 rounded-full bg-primary/30 blur-3xl" />
        <Link to="/" className="flex items-center gap-2 font-heading font-bold text-xl relative z-10" data-testid="auth-brand-link">
          <span className="w-9 h-9 rounded-xl bg-primary grid place-items-center"><Bot className="w-5 h-5" /></span>
          Resto<span className="text-primary">IA</span>
        </Link>
        <div className="relative z-10 max-w-md">
          <h2 className="font-heading text-3xl font-bold leading-tight">
            Votre réceptionniste IA qui prend vos commandes 24h/24.
          </h2>
          <p className="mt-4 text-white/70">
            Rejoignez les restaurants d'Abidjan qui automatisent leur prise de commande avec RestoIA.
          </p>
        </div>
        <p className="relative z-10 text-sm text-white/40">© {new Date().getFullYear()} RestoIA — Côte d'Ivoire</p>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 font-heading font-bold text-xl mb-8">
            <span className="w-8 h-8 rounded-lg bg-primary text-primary-foreground grid place-items-center"><Bot className="w-5 h-5" /></span>
            Resto<span className="text-primary">IA</span>
          </Link>
          <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-2 text-muted-foreground text-sm">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-sm text-muted-foreground text-center">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
