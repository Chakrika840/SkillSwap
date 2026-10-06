"""
Startup data: creates the admin account and (optionally) five demo users whose skills complement
each other, so Explore, smart matching and AI Picks have something to show immediately.
Runs once at startup (like Spring's CommandLineRunner) and never creates duplicates.
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from .config import settings
from .models import ProficiencyLevel, Role, Skill, SkillType, User
from .security import hash_password

log = logging.getLogger("skillswap.seed")

DEMO_PASSWORD = "demo1234"

DEMO_USERS = [
    ("Aarav Reddy", "aarav@demo.com", "Hyderabad", "Backend developer who loves clean APIs.",
     [("Java", "ADVANCED"), ("Spring Boot", "INTERMEDIATE")], [("Python", "BEGINNER"), ("UI Design", "BEGINNER")]),
    ("Diya Sharma", "diya@demo.com", "Hyderabad", "Data science student, happy to help with Python.",
     [("Python", "INTERMEDIATE"), ("Machine Learning", "BEGINNER")], [("Java", "INTERMEDIATE"), ("Public Speaking", "BEGINNER")]),
    ("Kiran Rao", "kiran@demo.com", "Bengaluru", "Product designer. Figma all day.",
     [("UI Design", "ADVANCED"), ("Figma", "INTERMEDIATE")], [("React", "BEGINNER"), ("Java", "BEGINNER")]),
    ("Meera Iyer", "meera@demo.com", "Hyderabad", "Frontend engineer, weekend guitarist in training.",
     [("React", "ADVANCED"), ("JavaScript", "ADVANCED")], [("Guitar", "BEGINNER"), ("Python", "BEGINNER")]),
    ("Rohan Das", "rohan@demo.com", "Chennai", "Musician and debate coach.",
     [("Guitar", "INTERMEDIATE"), ("Public Speaking", "ADVANCED")], [("Spring Boot", "BEGINNER"), ("Photography", "BEGINNER")]),
]


def seed(db: DbSession) -> None:
    admin_email = settings.admin_email.strip().lower()
    if not db.scalar(select(User.id).where(User.email == admin_email)):
        db.add(User(name="Admin", email=admin_email, password=hash_password(settings.admin_password), role=Role.ADMIN))
        log.info("Created admin account %s", admin_email)

    has_users = db.scalar(select(func.count(User.id)).where(User.role == Role.USER))
    if settings.seed_demo_users and not has_users:
        demo_hash = hash_password(DEMO_PASSWORD)
        for name, email, city, bio, teaches, wants in DEMO_USERS:
            user = User(name=name, email=email, city=city, bio=bio, password=demo_hash, role=Role.USER)
            for skill_name, level in teaches:
                user.skills.append(Skill(name=skill_name, level=ProficiencyLevel(level), type=SkillType.OFFERED))
            for skill_name, level in wants:
                user.skills.append(Skill(name=skill_name, level=ProficiencyLevel(level), type=SkillType.WANTED))
            db.add(user)          # skills are saved too, through the cascade
        log.info("Seeded %d demo users (password: %s)", len(DEMO_USERS), DEMO_PASSWORD)
    db.commit()
