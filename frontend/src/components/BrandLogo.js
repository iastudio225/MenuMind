import React from "react";
import { UtensilsCrossed } from "lucide-react";

const SIZES = {
  lg: { box: "w-10 h-10 rounded-xl", icon: "w-5 h-5" },
  sm: { box: "w-8 h-8 rounded-lg", icon: "w-4 h-4" },
};

export default function BrandLogo({ size = "lg", className = "" }) {
  const s = SIZES[size] || SIZES.lg;
  return (
    <span
      className={`${s.box} bg-primary text-primary-foreground grid place-items-center shrink-0 ${className}`}
      data-testid="brand-logo-icon"
    >
      <UtensilsCrossed className={s.icon} />
    </span>
  );
}
