"""
seed.py
-------
Populates the database with sample foods, tables, and a default admin
account so the app is immediately usable. Run once:

    python seed.py
"""

import os
from database import engine, SessionLocal, Base
import models
from auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

FOODS = [
    ("Chicken Biriyani", "Main Course", 180, "Spicy Kerala style biriyani with tender chicken", False, 3, "biriyani.jpg", 4.8),
    ("Chicken 65", "Starters", 160, "Crispy deep-fried spicy chicken starter", False, 3, "chicken65.jpg", 4.6),
    ("Paneer Butter Masala", "Main Course", 180, "Creamy tomato-based curry with soft paneer cubes", True, 2, "paneer_butter.jpg", 4.5),
    ("Veg Fried Rice", "Main Course", 140, "Wok-tossed rice with fresh vegetables", True, 1, "veg_fried_rice.jpg", 4.2),
    ("Chilli Paneer", "Starters", 220, "Indo-Chinese style spicy paneer starter", True, 3, "chilli_paneer.jpg", 4.4),
    ("Fresh Lime", "Beverages", 40, "Refreshing lime juice, sweet or salted", True, 1, "fresh_lime.jpg", 4.3),
    ("Mutton Curry", "Main Course", 260, "Slow-cooked mutton in a rich spicy gravy", False, 3, "mutton_curry.jpg", 4.7),
    ("Gulab Jamun", "Desserts", 80, "Soft milk dumplings soaked in sugar syrup", True, 1, "gulab_jamun.jpg", 4.6),
    ("Veg Spring Rolls", "Starters", 120, "Crispy rolls stuffed with mixed vegetables", True, 1, "spring_rolls.jpg", 4.1),
    ("Masala Dosa", "Main Course", 100, "Crispy rice crepe with spiced potato filling", True, 2, "masala_dosa.jpg", 4.5),
    ("Fish Fry", "Starters", 200, "Kerala style shallow fried fish with spices", False, 2, "fish_fry.jpg", 4.4),
    ("Curd Rice", "Main Course", 90, "Comforting mild rice with fresh curd", True, 1, "curd_rice.jpg", 4.0),
]

TABLES = [
    ("T-01", 2), ("T-02", 2), ("T-03", 4), ("T-04", 4),
    ("T-05", 4), ("T-06", 6), ("T-07", 6), ("T-08", 6),
    ("T-09", 8), ("T-10", 8),
]

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@keralacafe.local")
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "9999999999")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


def run():
    if db.query(models.Food).count() == 0:
        for name, category, price, desc, is_veg, spice, image, rating in FOODS:
            db.add(models.Food(
                food_name=name, category=category, price=price, description=desc,
                is_veg=is_veg, spice_level=spice, image_url=f"/static/images/{image}",
                availability=True, rating=rating,
            ))
        print(f"Seeded {len(FOODS)} foods.")
    else:
        print("Foods already seeded, skipping.")

    if db.query(models.RestaurantTable).count() == 0:
        for number, capacity in TABLES:
            db.add(models.RestaurantTable(table_number=number, capacity=capacity, status="available"))
        print(f"Seeded {len(TABLES)} tables.")
    else:
        print("Tables already seeded, skipping.")

    if db.query(models.User).filter(models.User.is_admin == True).count() == 0:  # noqa: E712
        db.add(models.User(
            name="Admin",
            email=ADMIN_EMAIL,
            phone=ADMIN_PHONE,
            password_hash=hash_password(ADMIN_PASSWORD),
            is_admin=True,
        ))
        print(f"Seeded admin account -> email: {ADMIN_EMAIL}  password: {ADMIN_PASSWORD}")
        print("(change this in production - set ADMIN_EMAIL/ADMIN_PHONE/ADMIN_PASSWORD env vars before seeding)")
    else:
        print("Admin account already exists, skipping.")

    db.commit()


if __name__ == "__main__":
    run()
    db.close()
