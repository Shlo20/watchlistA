"""Seed the DB with sample products and a starter buyer account.

Run once after migrations:
    python -m app.seed
"""
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.product import Product, ProductCategory
from app.models.user import User, UserRole


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


def main():
    # Create tables (in production use Alembic migrations instead).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            for name, cat, brand, model in SAMPLE_PRODUCTS:
                db.add(Product(name=name, category=cat, brand=brand, model=model))
            print(f"Seeded {len(SAMPLE_PRODUCTS)} products")

        if db.query(User).filter(User.role == UserRole.BUYER).count() == 0:
            db.add(User(
                name="Admin Buyer",
                phone="5555550100",
                carrier="att",
                password_hash=hash_password("changeme123"),
                role=UserRole.BUYER,
            ))
            print("Seeded buyer: phone=5555550100 password=changeme123")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
