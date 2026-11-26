import React from "react";
import { Sparkles } from "lucide-react";

/**
 * Landing-only brand mark. The shared `BrandLogo` keeps its restaurant icon for
 * the dashboard and auth screens; here the icon is intentionally neutral (AI).
 */
export default function LandingBrand() {
  return (
    <span className="flex items-center gap-2.5 font-heading font-bold text-xl" data-testid="brand-logo">
      <span className="relative grid h-10 w-10 place-items-center rounded-xl bg-[#0F172A] text-primary shadow-sm"
        data-testid="brand-logo-icon">
        <Sparkles className="h-5 w-5" aria-hidden="true" />
        <span aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary ring-2 ring-background" />
      </span>
      <span className="tracking-tight">Menu<span className="text-primary">Mind</span></span>
    </span>
  );
}
