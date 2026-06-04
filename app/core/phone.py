"""Phone number normalization utilities."""
import phonenumbers
from phonenumbers import NumberParseException


def normalize_phone(raw: str, region: str = "US") -> str:
    """Parse *raw* and return it in E.164 format (e.g. +16467522092).

    Raises ValueError for inputs that cannot be parsed or whose length is
    structurally impossible for the given region.
    """
    try:
        parsed = phonenumbers.parse(raw, region)
    except NumberParseException as exc:
        raise ValueError(f"Cannot parse phone number: {raw!r}") from exc
    if not phonenumbers.is_possible_number(parsed):
        raise ValueError(f"Invalid phone number: {raw!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
