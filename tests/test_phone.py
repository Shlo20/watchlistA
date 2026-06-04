"""Unit tests for app.core.phone.normalize_phone."""
import pytest

from app.core.phone import normalize_phone

CANONICAL = "+16467522092"


@pytest.mark.parametrize("raw", [
    "646-752-2092",
    "(646) 752 2092",
    "16467522092",
    "+16467522092",
])
def test_normalizes_to_e164(raw):
    assert normalize_phone(raw) == CANONICAL


def test_invalid_raises_value_error():
    with pytest.raises(ValueError):
        normalize_phone("not-a-phone")
