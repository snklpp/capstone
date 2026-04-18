"""Seed script — creates demo users for testing."""

import sys
import os

# Add the project root to the path so we can import `app`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base, SessionLocal
from app.models import User
from app.auth import hash_password


def seed():
    """Create demo users: admin, students, and verifier."""
    # Drop and recreate all tables for a clean slate
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    users = [
        {
            "username": "admin",
            "password": "admin123",
            "role": "admin",
            "student_id": None,
            "full_name": "Admin User",
        },
        {
            "username": "2021CS001",
            "password": "pass1234",
            "role": "student",
            "student_id": "2021CS001",
            "full_name": "Aarav Sharma",
        },
        {
            "username": "2021CS002",
            "password": "pass1234",
            "role": "student",
            "student_id": "2021CS002",
            "full_name": "Priya Patel",
        },
        {
            "username": "2021CS003",
            "password": "pass1234",
            "role": "student",
            "student_id": "2021CS003",
            "full_name": "Rohan Gupta",
        },
        {
            "username": "2021CS004",
            "password": "pass1234",
            "role": "student",
            "student_id": "2021CS004",
            "full_name": "Ananya Singh",
        },
        {
            "username": "2021CS005",
            "password": "pass1234",
            "role": "student",
            "student_id": "2021CS005",
            "full_name": "Vikram Reddy",
        },
        {
            "username": "verifier1",
            "password": "verifier123",
            "role": "verifier",
            "student_id": None,
            "full_name": "TCS Recruitment",
        },
    ]

    for u in users:
        user = User(
            username=u["username"],
            hashed_password=hash_password(u["password"]),
            role=u["role"],
            student_id=u["student_id"],
            full_name=u["full_name"],
        )
        db.add(user)
        print(f"  ✅ Created {u['role']:>8} → {u['username']:<12} ({u['full_name']})")

    db.commit()
    db.close()
    print(f"\nDone! {len(users)} users created.")


if __name__ == "__main__":
    print("🌱 Seeding database (clean reset)...\n")
    seed()
