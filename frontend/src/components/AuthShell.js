import React from "react";
import { Link } from "react-router-dom";
import { Clock3, MessageSquareText, QrCode } from "lucide-react";
import AveniqBrand from "@/components/AveniqBrand";

const BENEFITS = [
  { icon: Clock3, label: "Disponible 24h/24" },
  { icon: MessageSquareText, label: "Répond à partir de vos informations" },
  { icon: QrCode, label: "Widget, lien partagé et QR code" },
];

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">
      {/* Brand panel */}
      <div className="relative hidden flex-col justify-center overflow-hidden bg-foreground p-12 text-white lg:flex">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute -left-24 -top-24 h-80 w-80 rounded-full bg-primary/30 blur-3xl" />
          <div className="absolute -bottom-24 right-0 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
        </div>

        <div className="relative z-10 max-w-md">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-peach">
            AI Business Assistant
          </p>
          <p className="mt-3 font-heading text-3xl font-bold leading-tight">
            Votre assistant IA pour votre entreprise.
          </p>
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

        <p className="absolute bottom-12 left-12 z-10 text-sm text-white/40">
          © {new Date().getFullYear()} AVENIQ — Abidjan, Côte d'Ivoire
        </p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <Link to="/" data-testid="auth-brand-link"
            className="mb-8 inline-flex rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
            <AveniqBrand variant="light" className="h-9" testId="brand-logo-icon" alt="" />
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
