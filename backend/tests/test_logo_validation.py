"""RestaurantUpdate.logo — URL http(s) or uploaded image (browser data URL)."""
import pytest
from pydantic import ValidationError

from models import RestaurantUpdate

DATA_URL = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA=="


def test_accepts_public_url():
    doc = RestaurantUpdate(logo="https://cdn.example.com/logo.png")
    assert doc.logo == "https://cdn.example.com/logo.png"


def test_accepts_uploaded_image():
    doc = RestaurantUpdate(logo=DATA_URL)
    assert doc.logo == DATA_URL


def test_accepts_empty_and_none():
    assert RestaurantUpdate(logo="").logo == ""
    assert RestaurantUpdate(logo=None).logo is None


def test_rejects_unsafe_scheme():
    with pytest.raises(ValidationError):
        RestaurantUpdate(logo="javascript:alert(1)")


def test_rejects_fake_data_url():
    with pytest.raises(ValidationError):
        RestaurantUpdate(logo="data:text/html;base64,PHNjcmlwdD4=")


def test_rejects_oversized_logo():
    with pytest.raises(ValidationError):
        RestaurantUpdate(logo="https://cdn.example.com/" + "a" * 400_000)
