import React from "react";

/**
 * AVENIQ horizontal brand mark.
 *
 * - `light` : transparent PNG/WebP with the dark wordmark, for light surfaces
 *   (landing header/footer, dashboard sidebar, admin header, auth mobile).
 * - `dark`  : white wordmark inside the official navy card, for dark panels
 *   (auth left panel, dark CTA blocks).
 *
 * Assets come from the official 2026 kit. They are raster preview crops, not
 * vector files; the web derivatives in `public/brand/kit-2026/optimized/` only
 * remove the preview background. See `public/brand/kit-2026/README-INSTALL.md`.
 * Callers set the rendered height with `className` (e.g. "h-8", "h-9").
 */
const LOGOS = {
  light: {
    webp: "/brand/kit-2026/optimized/logo-horizontal-light.webp",
    png: "/brand/kit-2026/optimized/logo-horizontal-light.png",
    width: 303,
    height: 88,
  },
  dark: {
    webp: "/brand/kit-2026/optimized/logo-horizontal-dark.webp",
    png: "/brand/kit-2026/optimized/logo-horizontal-dark.png",
    width: 330,
    height: 118,
  },
};

export default function AveniqBrand({
  variant = "light",
  className = "h-9",
  alt = "AVENIQ — AI Business Assistant",
  testId,
}) {
  const logo = LOGOS[variant] || LOGOS.light;
  return (
    <picture>
      <source srcSet={logo.webp} type="image/webp" />
      <img src={logo.png} alt={alt} width={logo.width} height={logo.height} decoding="async"
        className={`w-auto shrink-0 ${className}`} data-testid={testId} />
    </picture>
  );
}
