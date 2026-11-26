import React from "react";
import { Link } from "react-router-dom";
import { Clock3, MessageSquareText, QrCode, Sparkles } from "lucide-react";

const BENEFITS = [
  { icon: Clock3, label: "Disponible 24h/24" },
  { icon: MessageSquareText, label: "Répond à partir de vos informations" },
  { icon: QrCode, label: "Widget, lien partagé et QR code" },
];

function AuthBrand({ compact = false, withTestId = false }) {
  return (
    <span className="flex items-center gap-2.5 font-heading font-bold text-xl">
      <span className={`relative grid ${compact ? "h-9 w-9 rounded-lg" : "h-11 w-11 rounded-xl"} place-items-center bg-[#0F172A] text-primary`}
        data-testid={withTestId ? "brand-logo-icon" : undefined}>
        <Sparkles className={compact ? "h-4 w-4" : "h-5 w-5"} aria-hidden="true" />
        <span aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary ring-2 ring-[#0F172A]" />
      </span>
      <span>Menu<span className="text-primary">Mind</span></span>
    </span>
  );
}

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-[#0F172A] p-12 text-white lg:flex">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full bg-primary/30 blur-3xl" />
          <div className="absolute -bottom-24 right-0 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
        </div>

        <Link to="/" data-testid="auth-brand-link"
          className="relative z-10 inline-flex w-fit rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-[#0F172A]">
          <AuthBrand withTestId />
        </Link>

        <div className="relative z-10 max-w-md">
          <h2 className="font-heading text-3xl font-bold leading-tight">
            Votre assistant IA pour votre entreprise.
          </h2>
          <p className="mt-4 text-white/70">
            Répondez à vos clients, centralisez les informations de votre entreprise
            et gagnez du temps au quotidien.
          </p>
          <ul className="mt-8 space-y-3">
            {BENEFITS.map(({ icon: Icon, label }) => (
              <li key={label} className="flex items-center gap-3 text-sm text-white/80">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/10 text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative z-10 text-sm text-white/40">
          © {new Date().getFullYear()} MenuMind — Abidjan, Côte d'Ivoire
        </p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <Link to="/" className="mb-8 inline-flex rounded-lg lg:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
            <AuthBrand compact />
          </Link>

          <div className="rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
            <h1 className="font-heading text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-6 text-center text-sm text-muted-foreground">{footer}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
