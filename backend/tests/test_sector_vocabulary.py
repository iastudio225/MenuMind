"""Phase C — vocabulaire secteur de l'agent IA (prompt + résolveur)."""
from services.ai.vocabulary import sector_vocab
from services.ai.deterministic_resolver import resolve


def test_vocab_restaurant_is_historical_default():
    vocab = sector_vocab("restaurant")
    assert vocab["business"] == "restaurant"
    assert vocab["item"] == "plat"
    assert vocab["greeting_question"] == "Que souhaitez-vous commander ?"
    assert vocab["delivery_fee_label"] == "Livraison"


def test_vocab_logistique():
    vocab = sector_vocab("logistique")
    assert vocab["business"] == "entreprise de livraison"
    assert vocab["item"] == "service"
    assert vocab["order"] == "demande de course"
    assert "course" in vocab["greeting_question"]
    assert vocab["fulfillment"] == "ramassage/livraison"


def test_vocab_ecommerce():
    vocab = sector_vocab("e-commerce")
    assert vocab["business"] == "boutique"
    assert vocab["item"] == "produit"
    assert "acheter" in vocab["greeting_question"]


def test_vocab_unknown_falls_back_to_restaurant():
    assert sector_vocab(None) == sector_vocab("restaurant")
    assert sector_vocab("inconnu") == sector_vocab("restaurant")


def test_greeting_is_sector_aware():
    logistique = {"name": "Mididd location", "secteur": "logistique"}
    ecommerce = {"name": "Awa Shop", "secteur": "e-commerce"}
    assert "réserver une course" in resolve("bonjour", logistique, {}, {})
    assert "acheter" in resolve("bonjour", ecommerce, {}, {})


def test_cart_summary_uses_sector_noun():
    restaurant = {"name": "Mididd location", "secteur": "logistique"}
    cart = {
        "items": [{"name": "Course express", "quantity": 1, "line_total": 2000}],
        "subtotal": 2000, "delivery_fee": 0, "total": 2000,
    }
    out = resolve("voir ma demande", restaurant, {}, cart)
    assert out is not None
    assert "Votre demande" in out
    assert "Total : 2 000 FCFA" in out
