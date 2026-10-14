export function formatFCFA(amount) {
  const n = Number(amount || 0);
  return `${n.toLocaleString("fr-FR").replace(/\u202f/g, " ")} FCFA`;
}

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Une erreur est survenue. Réessayez.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export const ROLE_LABELS = {
  SUPER_ADMIN: "Super Admin",
  RESTAURANT_OWNER: "Propriétaire",
  RESTAURANT_MANAGER: "Manager",
  RESTAURANT_STAFF: "Serveur / Cuisine",
};
