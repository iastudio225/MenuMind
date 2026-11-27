import React from "react";

const SIZES = {
  lg: "w-10 h-10 rounded-xl",
  sm: "w-8 h-8 rounded-lg",
};

/**
 * Compact AVENIQ app icon (kept for any future square-logo context).
 * Auth and navigation now use the horizontal `AveniqBrand` mark.
 */
export default function BrandLogo({ size = "lg", className = "" }) {
  const s = SIZES[size] || SIZES.lg;
  return (
    <span className={`block shrink-0 overflow-hidden ${s} ${className}`} data-testid="brand-logo-icon">
      <img src="/brand/kit-2026/optimized/app-icon-96.png" alt="" width={96} height={96}
        className="h-full w-full object-cover" />
    </span>
  );
}
