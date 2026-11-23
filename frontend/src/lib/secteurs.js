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
    // Dashboard
    dashboardNoun: "restaurant",
    ordersLabel: "Commandes",
    ordersTodayLabel: "Commandes aujourd'hui",
    ordersWeekLabel: "Commandes (7 jours)",
    pendingLabel: "Commandes en attente",
    preparingLabel: "En préparation",
    preparingHint: "Cuisine",
    avgBasketLabel: "Panier moyen",
    onboardingBannerTitle: "Terminez la configuration de votre restaurant",
    ctaTitle: "Votre restaurant, prêt à commander",
    ctaBody: "Gérez votre menu, recevez les commandes avec l'agent IA et suivez votre activité depuis ce tableau de bord.",
    orderTypeLabels: { DELIVERY: "Livraison", PICKUP: "Retrait", DINE_IN: "Sur place" },
    statusLabels: {
      PENDING: "En attente", CONFIRMED: "Confirmée", PREPARING: "En préparation",
      READY: "Prête", OUT_FOR_DELIVERY: "En livraison", DELIVERED: "Livrée", CANCELLED: "Annulée",
    },
    statusActions: {
      PENDING: [["CONFIRMED", "Confirmer", "check"]],
      CONFIRMED: [["PREPARING", "Préparer", "chef"]],
      PREPARING: [["READY", "Marquer prête", "package"]],
      READY: [["OUT_FOR_DELIVERY", "Mettre en livraison", "truck"], ["DELIVERED", "Marquer livrée", "check"]],
      OUT_FOR_DELIVERY: [["DELIVERED", "Marquer livrée", "check"]],
    },
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
    // Dashboard
    dashboardNoun: "entreprise",
    ordersLabel: "Courses",
    ordersTodayLabel: "Courses aujourd'hui",
    ordersWeekLabel: "Courses (7 jours)",
    pendingLabel: "Demandes en attente",
    preparingLabel: "En cours",
    preparingHint: "Assignation",
    avgBasketLabel: "Montant moyen",
    onboardingBannerTitle: "Terminez la configuration de votre entreprise",
    ctaTitle: "Votre entreprise, prête à recevoir des courses",
    ctaBody: "Gérez vos services de livraison, recevez les demandes avec l'agent IA et suivez votre activité depuis ce tableau de bord.",
    orderTypeLabels: { DELIVERY: "Course", PICKUP: "Retrait", DINE_IN: "—" },
    statusLabels: {
      PENDING: "Demande reçue", CONFIRMED: "Course acceptée", PREPARING: "Coursier assigné",
      READY: "Prêt au départ", OUT_FOR_DELIVERY: "En route", DELIVERED: "Livrée", CANCELLED: "Annulée",
    },
    statusActions: {
      PENDING: [["CONFIRMED", "Accepter la course", "check"]],
      CONFIRMED: [["PREPARING", "Assigner un coursier", "truck"]],
      PREPARING: [["READY", "Prêt au départ", "package"]],
      READY: [["OUT_FOR_DELIVERY", "Départ", "truck"], ["DELIVERED", "Marquer livrée", "check"]],
      OUT_FOR_DELIVERY: [["DELIVERED", "Marquer livrée", "check"]],
    },
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
    // Dashboard
    dashboardNoun: "boutique",
    ordersLabel: "Commandes",
    ordersTodayLabel: "Commandes aujourd'hui",
    ordersWeekLabel: "Commandes (7 jours)",
    pendingLabel: "Commandes en attente",
    preparingLabel: "En préparation",
    preparingHint: "Préparation",
    avgBasketLabel: "Panier moyen",
    onboardingBannerTitle: "Terminez la configuration de votre boutique",
    ctaTitle: "Votre boutique, prête à vendre",
    ctaBody: "Gérez votre catalogue, recevez les commandes avec l'agent IA et suivez votre stock depuis ce tableau de bord.",
    orderTypeLabels: { DELIVERY: "Livraison", PICKUP: "Retrait", DINE_IN: "—" },
    statusLabels: {
      PENDING: "Commande reçue", CONFIRMED: "Confirmée", PREPARING: "En préparation",
      READY: "Prête à expédier", OUT_FOR_DELIVERY: "Expédiée", DELIVERED: "Livrée", CANCELLED: "Annulée",
    },
    statusActions: {
      PENDING: [["CONFIRMED", "Confirmer", "check"]],
      CONFIRMED: [["PREPARING", "Préparer", "package"]],
      PREPARING: [["READY", "Prête à expédier", "package"]],
      READY: [["OUT_FOR_DELIVERY", "Expédier", "truck"], ["DELIVERED", "Marquer livrée", "check"]],
      OUT_FOR_DELIVERY: [["DELIVERED", "Marquer livrée", "check"]],
    },
  },
};

export const SECTEUR_OPTIONS = Object.values(SECTEURS);

export function secteurConfig(value) {
  return SECTEURS[value] || SECTEURS[SECTEUR_DEFAULT];
}
