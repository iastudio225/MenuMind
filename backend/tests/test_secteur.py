"""Contrats du champ `secteur` (restaurant / logistique / e-commerce)."""
import pytest
from pydantic import ValidationError

from models import (
    RegisterBody, RestaurantUpdate, AdminRestaurantCreate, AdminRestaurantUpdate,
    normalize_secteur, validate_secteur,
    SECTEUR_RESTAURANT, SECTEUR_LOGISTIQUE, SECTEUR_ECOMMERCE,
)
from routers.auth_router import default_widget_message


def test_normalize_secteur_falls_back_to_restaurant():
    assert normalize_secteur(None) == SECTEUR_RESTAURANT
    assert normalize_secteur("inconnu") == SECTEUR_RESTAURANT
    assert normalize_secteur(SECTEUR_RESTAURANT) == SECTEUR_RESTAURANT


def test_normalize_secteur_keeps_known_sectors():
    assert normalize_secteur(SECTEUR_LOGISTIQUE) == SECTEUR_LOGISTIQUE
    assert normalize_secteur(SECTEUR_ECOMMERCE) == SECTEUR_ECOMMERCE


def test_validate_secteur_rejects_unknown():
    assert validate_secteur(None) is None
    assert validate_secteur(SECTEUR_LOGISTIQUE) == SECTEUR_LOGISTIQUE
    with pytest.raises(ValueError):
        validate_secteur("inconnu")


def test_register_body_defaults_to_restaurant():
    body = RegisterBody(name="Awa", email="awa@example.ci", password="secret1",
                        restaurant_name="Chez Awa")
    assert body.secteur == SECTEUR_RESTAURANT


def test_register_body_accepts_known_sector():
    body = RegisterBody(name="Awa", email="awa@example.ci", password="secret1",
                        restaurant_name="Awa Express", secteur=SECTEUR_LOGISTIQUE)
    assert body.secteur == SECTEUR_LOGISTIQUE


def test_register_body_rejects_unknown_sector():
    with pytest.raises(ValidationError):
        RegisterBody(name="Awa", email="awa@example.ci", password="secret1",
                     restaurant_name="Awa Express", secteur="inconnu")


@pytest.mark.parametrize("model,payload", [
    (RestaurantUpdate, {"secteur": SECTEUR_ECOMMERCE}),
    (AdminRestaurantUpdate, {"secteur": SECTEUR_ECOMMERCE}),
    (AdminRestaurantCreate, {"name": "Boutique", "owner_name": "Awa",
                             "owner_email": "awa@example.ci",
                             "owner_password": "secret1",
                             "secteur": SECTEUR_ECOMMERCE}),
])
def test_update_models_accept_known_sector(model, payload):
    assert model(**payload).secteur == SECTEUR_ECOMMERCE


def test_update_models_reject_unknown_sector():
    with pytest.raises(ValidationError):
        RestaurantUpdate(secteur="inconnu")
    with pytest.raises(ValidationError):
        AdminRestaurantUpdate(secteur="inconnu")


def test_default_widget_message_is_sector_aware():
    assert "commander" in default_widget_message("Chez Awa", SECTEUR_RESTAURANT)
    assert "course" in default_widget_message("Awa Express", SECTEUR_LOGISTIQUE)
    assert "boutique" in default_widget_message("Awa Shop", SECTEUR_ECOMMERCE)
