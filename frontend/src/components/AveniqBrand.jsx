import React from "react";

/**
 * AVENIQ horizontal brand mark (foundation component).
 *
 * - `light` : transparent PNG/WebP with the dark wordmark, for light surfaces
 *   (landing header/footer, dashboard sidebar, admin header, auth mobile).
 * - `dark`  : wordmark on the brand navy background, for dark panels
 *   (auth left panel, dark CTA blocks).
 *
 * Intrinsic size is 720x240; callers set the rendered height with `className`
 * (e.g. "h-8", "h-9"). The original brand-kit files stay untouched in
 * `public/brand/logos/`.
 */
const LOGOS = {
  light: {
    webp: "/brand/optimized/logo-light-720.webp",
    png: "/brand/optimized/logo-light-720.png",
  },
  dark: {
    webp: "/brand/optimized/logo-dark-720.webp",
    png: "/brand/optimized/logo-dark-720.png",
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
      <img src={logo.png} alt={alt} width={720} height={240} decoding="async"
        className={`w-auto ${className}`} data-testid={testId} />
    </picture>
  );
}
