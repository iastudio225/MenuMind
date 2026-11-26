import React from "react";
import { Link } from "react-router-dom";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";
import LandingBrand from "./LandingBrand";

const NAV_LINKS = [
  { href: "#features", label: "Produit", testid: "nav-features-link", mobileTestid: "nav-mobile-product" },
  { href: "#solutions", label: "Solutions", testid: "nav-solutions-link", mobileTestid: "nav-mobile-solutions" },
  { href: "#pricing", label: "Tarifs", testid: "nav-pricing-link", mobileTestid: "nav-mobile-pricing" },
  { href: "/experience/rest_demo_chezawa", label: "Démo", testid: "nav-demo-link", mobileTestid: "nav-mobile-demo", route: true },
];

function NavItem({ link, className, testid }) {
  const props = { className, "data-testid": testid || link.testid };
  return link.route
    ? <Link to={link.href} {...props}>{link.label}</Link>
    : <a href={link.href} {...props}>{link.label}</a>;
}

export default function LandingNav() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <Link to="/" aria-label="MenuMind — accueil"
          className="shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
          <LandingBrand />
        </Link>

        <nav className="hidden items-center gap-8 text-sm font-medium text-muted-foreground md:flex"
          aria-label="Navigation principale">
          {NAV_LINKS.map((link) => (
            <NavItem key={link.testid} link={link} className="transition-colors hover:text-foreground" />
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link to="/login" className="hidden md:block">
            <Button variant="ghost" data-testid="nav-login-btn">Connexion</Button>
          </Link>
          <Link to="/register" className="hidden md:block">
            <Button data-testid="nav-register-btn">Commencer</Button>
          </Link>

          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="md:hidden" aria-label="Ouvrir le menu"
                data-testid="nav-mobile-trigger">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[85vw] max-w-sm" data-testid="nav-mobile-menu">
              <SheetHeader className="text-left">
                <SheetTitle className="font-heading">Menu</SheetTitle>
                <SheetDescription className="sr-only">Navigation principale MenuMind</SheetDescription>
              </SheetHeader>

              <nav className="mt-8 flex flex-col gap-1" aria-label="Navigation mobile">
                {NAV_LINKS.map((link) => {
                  const className = "block rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-secondary";
                  const item = link.route
                    ? <Link to={link.href} className={className} data-testid={link.mobileTestid}>{link.label}</Link>
                    : <a href={link.href} className={className} data-testid={link.mobileTestid}>{link.label}</a>;
                  return <SheetClose asChild key={link.testid}>{item}</SheetClose>;
                })}
              </nav>

              <div className="mt-8 space-y-3 border-t border-border pt-6">
                <SheetClose asChild>
                  <Link to="/login" data-testid="nav-mobile-login"
                    className="block rounded-lg px-3 py-3 text-base font-medium text-foreground transition-colors hover:bg-secondary">
                    Connexion
                  </Link>
                </SheetClose>
                <SheetClose asChild>
                  <Link to="/register" data-testid="nav-mobile-register">
                    <Button size="lg" className="w-full">Commencer</Button>
                  </Link>
                </SheetClose>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
