export function buildExperienceUrl(origin, publicId) {
  if (!origin || !publicId) return "";
  return `${origin.replace(/\/+$/, "")}/experience/${encodeURIComponent(publicId)}`;
}
