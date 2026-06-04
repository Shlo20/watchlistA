"""WhatsApp click-to-chat link builder and list body formatter."""
from urllib.parse import quote


def build_wa_link(phone: str, body: str) -> str:
    """Return a wa.me link for the given E.164 phone and message body.

    Strips the leading '+' so the URL is https://wa.me/16467522092?text=…
    The body is percent-encoded so special characters survive the URL.
    """
    digits = phone.lstrip("+")
    return f"https://wa.me/{digits}?text={quote(body, safe='')}"


def format_list_body(lst, items) -> str:
    """Render a List and its items as a clean WhatsApp message.

    Title (if present) is wrapped in *bold*. Each item is one line.
    """
    lines = []
    if lst.title:
        lines.append(f"*{lst.title}*")
    for item in items:
        name = (
            (item.product.name if item.product else None)
            or item.custom_product_name
            or "Item"
        )
        lines.append(f"- {item.quantity}x {name}")
    return "\n".join(lines)
