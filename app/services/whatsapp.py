"""WhatsApp click-to-chat link builder and list body formatter."""
from urllib.parse import quote


def build_wa_link(phone: str, body: str) -> str:
    """Return a wa.me link for the given E.164 phone and message body.

    Strips the leading '+' so the URL is https://wa.me/16467522092?text=…
    The body is percent-encoded so special characters survive the URL.
    """
    digits = phone.lstrip("+")
    return f"https://wa.me/{digits}?text={quote(body, safe='')}"


def format_list_body(lst, items, business_name: str | None = None) -> str:
    """Render a List and its items as a clean WhatsApp message.

    Title (if present) is wrapped in *bold*. Each item is one line.
    If business_name is set, prepends "Order from {business_name}" header.
    """
    lines = []
    if business_name:
        lines.append(f"Order from {business_name}")
        lines.append("")
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


def format_priced_body(lst, items, price_map: dict, business_name: str | None = None) -> str:
    """Render a list with unit prices and a running total for a WhatsApp quote.

    price_map: {list_item_id: unit_price_cents | None}
    Items with no price are included without a price. Total line is added when
    at least one price is set. If business_name is set, prepends a header line.
    """
    lines = []
    if business_name:
        lines.append(f"Order from {business_name}")
        lines.append("")
    if lst and lst.title:
        lines.append(f"*{lst.title}*")
    total_cents = 0
    has_prices = False
    for item in items:
        name = (
            (item.product.name if item.product else None)
            or item.custom_product_name
            or "Item"
        )
        price_cents = price_map.get(item.id)
        if price_cents is not None:
            has_prices = True
            total_cents += price_cents * item.quantity
            lines.append(f"- {item.quantity}x {name} — ${price_cents / 100:.2f} ea")
        else:
            lines.append(f"- {item.quantity}x {name}")
    if has_prices:
        lines.append(f"Total: ${total_cents / 100:.2f}")
    return "\n".join(lines)
