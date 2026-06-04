"""Seed the DB with sample products and two starter accounts.

Run once after migrations:
    python -m app.seed
"""
from app.core.database import Base, SessionLocal, engine
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.models.product import Product, ProductCategory
from app.models.user import User


SAMPLE_PRODUCTS = [
    ("iPhone 15 Pro", ProductCategory.PHONE, "Apple", "iPhone 15 Pro"),
    ("iPhone 15", ProductCategory.PHONE, "Apple", "iPhone 15"),
    ("Samsung Galaxy S24", ProductCategory.PHONE, "Samsung", "Galaxy S24"),
    ("iPad Air 11\"", ProductCategory.TABLET, "Apple", "iPad Air"),
    ("iPhone 15 Silicone Case", ProductCategory.CASE, "Apple", "iPhone 15"),
    ("iPhone 15 Pro OtterBox", ProductCategory.CASE, "OtterBox", "iPhone 15 Pro"),
    ("iPhone 15 Tempered Glass", ProductCategory.SCREEN_PROTECTOR, "Generic", "iPhone 15"),
    ("iPad Air Screen Protector", ProductCategory.SCREEN_PROTECTOR, "Generic", "iPad Air"),
]

SAMPLE_USERS = [
    ("Alice", "646-555-0100", "att", "changeme123"),
    ("Bob", "646-555-0101", "verizon", "changeme123"),
]


def main():
    # Create tables (in production use Alembic migrations instead).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            for name, cat, brand, model in SAMPLE_PRODUCTS:
                db.add(Product(name=name, category=cat, brand=brand, model=model))
            print(f"Seeded {len(SAMPLE_PRODUCTS)} products")

        if db.query(User).count() == 0:
            for name, raw_phone, carrier, password in SAMPLE_USERS:
                db.add(User(
                    name=name,
                    phone=normalize_phone(raw_phone),
                    carrier=carrier,
                    password_hash=hash_password(password),
                ))
            print(f"Seeded {len(SAMPLE_USERS)} users (password: changeme123)")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
