import { normalizeSource } from "./attribution";

export function buildExperienceUrl(origin, publicId) {
  if (!origin || !publicId) return "";
  return `${origin.replace(/\/+$/, "")}/experience/${encodeURIComponent(publicId)}`;
}

/**
 * Short share URL with a source marker: `/s/<publicId>?src=wa`.
 * nginx proxies `/s/` to the backend Open Graph card, which redirects humans
 * to the experience page and serves the tags to social crawlers.
 */
export function buildShareUrl(origin, publicId, source = "direct") {
  if (!origin || !publicId) return "";
  const base = `${origin.replace(/\/+$/, "")}/s/${encodeURIComponent(publicId)}`;
  const src = normalizeSource(source);
  return src === "direct" ? base : `${base}?src=${src}`;
}
