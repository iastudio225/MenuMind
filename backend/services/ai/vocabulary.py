"""Sector-specific vocabulary for the public AI agent (Phase C).

Keep the agent's client-facing nouns aligned with the tenant's sector without
duplicating the prompt in three variants. Internal tool names and statuses do
not change.
"""
from models import SECTEUR_RESTAURANT, SECTEUR_LOGISTIQUE, SECTEUR_ECOMMERCE

_VOCAB = {
    SECTEUR_RESTAURANT: {
        "business": "restaurant",
        "business_phrase": "du restaurant",
        "another_business": "un autre restaurant",
        "catalogue": "menu",
        "catalogue_cap": "Menu",
        "menu_section": "MENU DISPONIBLE",
        "cart": "panier",
        "cart_section": "PANIER ACTUEL",
        "item": "plat",
        "items": "plats",
        "order": "commande",
        "order_cap": "Commande",
        "day_menu_phrases": "le menu du jour, la carte du jour ou le plat du jour",
        "day_menu_short": "menu du jour",
        "recommend": "envie, goût, type de plat",
        "fulfillment": "livraison/retrait",
        "greeting_question": "Que souhaitez-vous commander ?",
        "delivery_fee_label": "Livraison",
    },
    SECTEUR_LOGISTIQUE: {
        "business": "entreprise de livraison",
        "business_phrase": "de l'entreprise de livraison",
        "another_business": "une autre entreprise",
        "catalogue": "catalogue de services",
        "catalogue_cap": "Catalogue de services",
        "menu_section": "CATALOGUE DE SERVICES DISPONIBLE",
        "cart": "demande",
        "cart_section": "DEMANDE ACTUELLE",
        "item": "service",
        "items": "services",
        "order": "demande de course",
        "order_cap": "Demande de course",
        "day_menu_phrases": "les services du jour",
        "day_menu_short": "services du jour",
        "recommend": "type de course, urgence, véhicule",
        "fulfillment": "ramassage/livraison",
        "greeting_question": "Souhaitez-vous réserver une course ?",
        "delivery_fee_label": "Frais de course",
    },
    SECTEUR_ECOMMERCE: {
        "business": "boutique",
        "business_phrase": "de la boutique",
        "another_business": "une autre boutique",
        "catalogue": "catalogue",
        "catalogue_cap": "Catalogue",
        "menu_section": "CATALOGUE DISPONIBLE",
        "cart": "panier",
        "cart_section": "PANIER ACTUEL",
        "item": "produit",
        "items": "produits",
        "order": "commande",
        "order_cap": "Commande",
        "day_menu_phrases": "la sélection du jour",
        "day_menu_short": "sélection du jour",
        "recommend": "envie, catégorie de produit",
        "fulfillment": "livraison/retrait",
        "greeting_question": "Que souhaitez-vous acheter ?",
        "delivery_fee_label": "Livraison",
    },
}


def sector_vocab(secteur) -> dict:
    return _VOCAB.get(secteur or SECTEUR_RESTAURANT, _VOCAB[SECTEUR_RESTAURANT])
