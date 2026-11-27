import React from "react";
import AveniqBrand from "@/components/AveniqBrand";

/**
 * Landing header brand: the AVENIQ horizontal logo (light variant).
 * The wrapper keeps the historical `brand-logo` testid; the image keeps
 * `brand-logo-icon` so existing automation keeps working.
 */
export default function LandingBrand() {
  return (
    <span className="flex items-center" data-testid="brand-logo">
      <AveniqBrand variant="light" className="h-8 sm:h-9" testId="brand-logo-icon" alt="" />
    </span>
  );
}
