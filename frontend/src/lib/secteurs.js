/**
 * Configuration d'affichage par secteur d'activité.
 * Source de vérité backend : backend/models.py (SECTEURS).
 * Tout secteur inconnu retombe sur "restaurant" (rétro-compatibilité).
 */
export const SECTEUR_DEFAULT = "restaurant";

export const SECTEURS = {
  restaurant: {
    value: "restaurant",
    label: "Restaurant",
    businessLabel: "Nom du restaurant",
    businessPlaceholder: "Chez Awa",
    businessNoun: "restaurant",
    catalogueLabel: "Menu",
    itemLabel: "Plat",
    itemsPlural: "plats",
    ctaLabel: "Commander",
    cartLabel: "Panier",
    cartViewLabel: "Voir le panier",
    orderNoun: "commande",
    pickupLabel: "À emporter",
    emptyCartText: "Votre panier est vide. Ajoutez des plats depuis le menu.",
    confirmationText: "Le restaurant prépare votre commande. 🍽️",
  },
  logistique: {
    value: "logistique",
    label: "Logistique / Livraison",
    businessLabel: "Nom de l'entreprise",
    businessPlaceholder: "Abidjan Express",
    businessNoun: "entreprise",
    catalogueLabel: "Services",
    itemLabel: "Service",
    itemsPlural: "services",
    ctaLabel: "Réserver",
    cartLabel: "Demande",
    cartViewLabel: "Voir la demande",
    orderNoun: "demande",
    pickupLabel: "Retrait",
    emptyCartText: "Votre demande est vide. Ajoutez des services depuis le catalogue.",
    confirmationText: "Votre course est en cours de traitement. 🚚",
  },
  "e-commerce": {
    value: "e-commerce",
    label: "E-commerce / Boutique",
    businessLabel: "Nom de la boutique",
    businessPlaceholder: "Abidjan Market",
    businessNoun: "boutique",
    catalogueLabel: "Catalogue",
    itemLabel: "Produit",
    itemsPlural: "produits",
    ctaLabel: "Ajouter au panier",
    cartLabel: "Panier",
    cartViewLabel: "Voir le panier",
    orderNoun: "commande",
    pickupLabel: "Retrait",
    emptyCartText: "Votre panier est vide. Ajoutez des produits depuis le catalogue.",
    confirmationText: "Votre commande est en préparation. 📦",
  },
};

export const SECTEUR_OPTIONS = Object.values(SECTEURS);

export function secteurConfig(value) {
  return SECTEURS[value] || SECTEURS[SECTEUR_DEFAULT];
}
