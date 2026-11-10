"""Pure unit tests for the deterministic chatbot resolver (no DB/network)."""
from services.ai.deterministic_resolver import resolve


def _restaurant(**updates):
    return {"name": "Chez Awa", **updates}


def _menu(*items):
    return {"categories": [{"items": list(items)}]}


def test_greeting_and_accented_hours_are_deterministic():
    assert resolve("Bonjour !", _restaurant(), _menu(), {}) == (
        "Bonjour et bienvenue chez Chez Awa ! Que souhaitez-vous commander ?")
    hours = {"monday": {"open": "09:00", "close": "18:00", "closed": False}}
    answer = resolve("Quels sont vos horaires ?", _restaurant(opening_hours=hours), _menu(), {})
    assert answer == "Voici nos horaires :\nLundi : 09:00–18:00"


def test_unconfigured_registration_hours_are_not_presented_as_real():
    restaurant = _restaurant(onboarding_completed=False, opening_hours={
        "monday": {"open": "11:00", "close": "22:00", "closed": False}})
    answer = resolve("A quelle heure ouvrez-vous ?", restaurant, _menu(), {})
    assert answer == "Les horaires ne sont pas renseignés pour le moment."


def test_exact_product_price_and_availability_are_grounded_in_catalog():
    menu = _menu({"name": "Poulet braisé", "price": 5000, "available": False})
    price = resolve("Quel est le prix du poulet braisé ?", _restaurant(), menu, {})
    status = resolve("Le poulet braisé est-il disponible ?", _restaurant(), menu, {})
    assert price == "Le prix de Poulet braisé est de 5 000 FCFA."
    assert status == "Poulet braisé est temporairement indisponible."


def test_specific_combo_name_wins_over_its_base_dish():
    menu = _menu({"name": "Poulet braisé", "price": 5000},
                 {"name": "Poulet braisé + alloco", "price": 6500})
    answer = resolve("Quel est le prix du Poulet braisé + alloco ?", _restaurant(), menu, {})
    assert answer == "Le prix de Poulet braisé + alloco est de 6 500 FCFA."


def test_ambiguous_product_and_unknown_intents_fall_back():
    menu = _menu({"name": "Poulet braisé", "price": 5000},
                 {"name": "Poulet braisé", "price": 6500})
    assert resolve("Quel est le prix du poulet braisé ?", _restaurant(), menu, {}) is None
    assert resolve("Aidez-moi à choisir un plat", _restaurant(), menu, {}) is None


def test_order_commands_are_not_misclassified_as_read_only_questions():
    menu = _menu({"name": "Poulet braisé", "price": 5000})
    assert resolve("Ajoute le poulet braisé au panier", _restaurant(), menu, {}) is None
    assert resolve("Combien de poulets braisés ?", _restaurant(), menu, {}) is None
    assert resolve("Livrer à cette adresse : 12 rue des Jardins", _restaurant(), menu, {}) is None


def test_contact_never_exposes_private_email_and_cart_uses_server_totals():
    restaurant = _restaurant(address="12 rue des Jardins", city="Abidjan",
                             phone="0700000000", email="private@example.test")
    contact = resolve("Quelle est votre adresse ?", restaurant, _menu(), {})
    assert "12 rue des Jardins, Abidjan" in contact
    assert "private@example.test" not in contact
    cart = {"items": [{"name": "Poulet", "quantity": 2, "line_total": 10000, "options": []}],
            "subtotal": 10000, "delivery_fee": 1000, "total": 11000}
    summary = resolve("Montre le récapitulatif de mon panier", _restaurant(), _menu(), cart)
    assert "2 × Poulet — 10 000 FCFA" in summary
    assert "Total : 11 000 FCFA" in summary
