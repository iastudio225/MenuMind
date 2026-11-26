import React from "react";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";

const FOOTER_LINKS = [
  { href: "#features", label: "Produit", testid: "footer-link-product" },
  { href: "#pricing", label: "Tarifs", testid: "footer-link-pricing" },
  { href: "/experience/rest_demo_chezawa", label: "Démo", testid: "footer-link-demo", route: true },
];

function FooterBrand() {
  return (
    <span className="flex items-center gap-2.5 font-heading text-lg font-bold">
      <span className="relative grid h-9 w-9 place-items-center rounded-lg bg-[#0F172A] text-primary">
        <Sparkles className="h-4 w-4" aria-hidden="true" />
        <span aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-primary ring-2 ring-background" />
      </span>
      <span>Menu<span className="text-primary">Mind</span></span>
    </span>
  );
}

export default function LandingFooter() {
  return (
    <footer className="border-t border-border bg-background" data-testid="landing-footer">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <Link to="/" aria-label="MenuMind — accueil"
              className="inline-flex rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
              <FooterBrand />
            </Link>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              L'assistant IA qui accompagne vos clients, répond à leurs questions et facilite
              vos interactions avec votre entreprise.
            </p>
          </div>

          <nav aria-label="Navigation de pied de page" className="flex flex-wrap gap-x-6 gap-y-2 md:justify-end">
            {FOOTER_LINKS.map((link) => (
              link.route
                ? <Link key={link.testid} to={link.href} data-testid={link.testid}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    {link.label}
                  </Link>
                : <a key={link.testid} href={link.href} data-testid={link.testid}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground">
                    {link.label}
                  </a>
            ))}
          </nav>
        </div>

        <div className="mt-8 flex flex-col gap-2 border-t border-border pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>© {new Date().getFullYear()} MenuMind — Tous droits réservés.</p>
          <p>Abidjan, Côte d'Ivoire</p>
        </div>
      </div>
    </footer>
  );
}
