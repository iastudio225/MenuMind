"""High-confidence, read-only answers for common public chatbot questions.

This module deliberately returns ``None`` for anything ambiguous so the
existing AI agent remains the fallback for free-form conversation.
"""
import re
import unicodedata


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _has(text: str, *phrases: str) -> bool:
    return any(re.search(r"(?:^|\s)" + re.escape(_normalize(p)) + r"(?:$|\s)", text) for p in phrases)


def _format_fcfa(value) -> str:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return ""
    return f"{amount:,}".replace(",", " ") + " FCFA"


def _items(menu):
    for category in (menu or {}).get("categories", []):
        for item in category.get("items", []):
            yield item


def _match_product(text: str, menu: dict):
    matches = []
    for item in _items(menu):
        name = _normalize(item.get("name", ""))
        if name and re.search(r"(?:^|\s)" + re.escape(name) + r"(?:$|\s)", text):
            matches.append((len(name), item))
    if not matches:
        return None
    # Prefer the longest explicit product phrase (e.g. a combo name also
    # contains the base dish name); duplicate equally-specific names remain
    # ambiguous and are left to the existing AI path.
    longest = max(length for length, _ in matches)
    best = [item for length, item in matches if length == longest]
    return best[0] if len(best) == 1 else None


def _valid_time(value) -> bool:
    match = re.fullmatch(r"(\d{2}):(\d{2})", str(value or ""))
    return bool(match and int(match.group(1)) < 24 and int(match.group(2)) < 60)


def _hours_answer(restaurant: dict) -> str:
    # New restaurants receive placeholder 11:00–22:00 values at registration.
    # Until onboarding is complete those values are not confirmed by the owner.
    if restaurant.get("onboarding_completed") is False:
        return "Les horaires ne sont pas renseignés pour le moment."
    hours = restaurant.get("opening_hours")
    days = (("monday", "lundi"), ("tuesday", "mardi"), ("wednesday", "mercredi"),
            ("thursday", "jeudi"), ("friday", "vendredi"), ("saturday", "samedi"),
            ("sunday", "dimanche"))
    lines = []
    for key, label in days:
        entry = (hours or {}).get(key)
        if not isinstance(entry, dict):
            continue
        if entry.get("closed") is True:
            lines.append(f"{label.capitalize()} : fermé")
        elif _valid_time(entry.get("open")) and _valid_time(entry.get("close")):
            lines.append(f"{label.capitalize()} : {entry['open']}–{entry['close']}")
    if not lines:
        return "Les horaires ne sont pas renseignés pour le moment."
    return "Voici nos horaires :\n" + "\n".join(lines)


def _contact_answer(message: str, restaurant: dict) -> str:
    text = _normalize(message)
    wants_address = _has(text, "adresse", "localisation", "situe", "situer", "trouver") or "ou se trouve" in text
    wants_phone = _has(text, "telephone", "numero", "appeler", "joindre", "contact", "whatsapp")
    address = ", ".join(str(restaurant.get(k)).strip() for k in ("address", "city") if restaurant.get(k))
    contacts = []
    for label, field in (("Téléphone", "phone"), ("WhatsApp", "whatsapp")):
        value = str(restaurant.get(field) or "").strip()
        if value and value not in [v for _, v in contacts]:
            contacts.append((label, value))
    if wants_address and wants_phone:
        parts = []
        parts.append(f"Adresse : {address}." if address else "L’adresse n’est pas renseignée.")
        parts.extend(f"{label} : {value}." for label, value in contacts)
        if not contacts:
            parts.append("Aucun contact public n’est renseigné.")
        return " ".join(parts)
    if wants_address:
        if address:
            return f"Notre adresse est : {address}."
        if contacts:
            return f"L’adresse n’est pas renseignée. Vous pouvez nous contacter au {contacts[0][1]}."
        return "L’adresse n’est pas renseignée et aucun contact public n’est disponible."
    if contacts:
        return "Vous pouvez nous contacter : " + " ; ".join(f"{label} : {value}" for label, value in contacts) + "."
    return "Aucun numéro de contact public n’est renseigné pour le moment."


def _cart_answer(cart_view: dict) -> str:
    lines = []
    for item in cart_view.get("items", []):
        name = str(item.get("name") or "Article")
        line = f"{item.get('quantity', 0)} × {name}"
        options = [str(option.get("name")) for option in item.get("options", []) if option.get("name")]
        if options:
            line += " (" + ", ".join(options) + ")"
        amount = _format_fcfa(item.get("line_total"))
        if amount:
            line += f" — {amount}"
        lines.append(line)
    if not lines:
        return "Votre panier est vide pour le moment."
    total = _format_fcfa(cart_view.get("total"))
    subtotal = _format_fcfa(cart_view.get("subtotal"))
    delivery = _format_fcfa(cart_view.get("delivery_fee"))
    summary = "Votre panier :\n" + "\n".join(lines)
    if subtotal:
        summary += f"\nSous-total : {subtotal}"
    if delivery and int(cart_view.get("delivery_fee") or 0):
        summary += f"\nLivraison : {delivery}"
    if total:
        summary += f"\nTotal : {total}"
    return summary


def _contact_intent(text: str):
    address_query = (
        _has(text, "adresse", "localisation")
        and (_has(text, "quelle", "quel", "donne", "indiquer", "situe", "situer", "trouver")
             or "ou se trouve" in text or "votre adresse" in text or "adresse du restaurant" in text)
    ) or "ou etes vous" in text or "ou se situe" in text
    phone_query = (
        _has(text, "telephone", "numero", "whatsapp", "contact")
        and (_has(text, "quel", "quelle", "votre", "comment", "donne", "indiquer")
             or "comment vous joindre" in text or "comment vous contacter" in text)
    ) or _has(text, "appeler", "joindre")
    return address_query, phone_query


def resolve(message: str, restaurant: dict, menu: dict, cart_view: dict):
    """Return a French answer for supported intents, otherwise ``None``."""
    text = _normalize(message)
    name = str(restaurant.get("name") or "notre restaurant")

    if text in {"bonjour", "bonsoir", "salut", "coucou"}:
        return f"Bonjour et bienvenue chez {name} ! Que souhaitez-vous commander ?"

    if (_has(text, "horaire", "horaires", "ouverture", "fermeture")
            or ("quelle heure" in text and _has(text, "ouvrez", "fermez"))
            or "quand ouvrez" in text or "quand fermez" in text):
        return _hours_answer(restaurant)

    wants_address, wants_contact = _contact_intent(text)
    if wants_address or wants_contact:
        return _contact_answer(message, restaurant)

    if (_has(text, "panier")
            and (_has(text, "recapitulatif", "resume", "contenu", "total", "voir", "afficher", "montre", "liste")
                 or "combien dans le panier" in text)):
        return _cart_answer(cart_view or {})

    asks_price = (_has(text, "prix", "coute", "tarif") or "quel est le prix" in text
                  or (_has(text, "combien") and "combien de" not in text))
    asks_availability = _has(text, "disponible", "disponibilite", "dispo")
    if asks_price or asks_availability:
        item = _match_product(text, menu or {})
        if item is None:
            return None
        product = item.get("name") or "Cet article"
        if asks_price and asks_availability:
            price = _format_fcfa(item.get("price"))
            price_text = f" Son prix est de {price}." if price else ""
            status = "disponible" if item.get("available", True) else "temporairement indisponible"
            return f"{product} est {status}.{price_text}"
        if asks_availability:
            status = "disponible" if item.get("available", True) else "temporairement indisponible"
            return f"{product} est {status}."
        price = _format_fcfa(item.get("price"))
        return f"Le prix de {product} est de {price}." if price else None

    return None
