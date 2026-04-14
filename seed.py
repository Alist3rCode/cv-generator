"""
seed.py — Données initiales pour démarrer l'application

Lance ce script UNE SEULE FOIS après la première installation :
  python seed.py

Crée :
  - Une organisation "Ma Société"
  - Un utilisateur admin (admin@example.com / admin1234)
  - Les langues Français et English
"""

import uuid
from database import SessionLocal, init_db
from models import Organisation, User, UserOrganisation, Language, RoleEnum
from routers.auth import hash_password

def seed():
    init_db()
    db = SessionLocal()

    # Organisation
    org = db.query(Organisation).filter(Organisation.nom == "Ma Société").first()
    if not org:
        org = Organisation(id=uuid.uuid4(), nom="Ma Société")
        db.add(org)
        db.flush()
        print(f"Organisation créée : {org.nom} (id={org.id})")
    else:
        print("Organisation déjà existante.")

    # Admin
    admin = db.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            password_hash=hash_password("admin1234"),
            nom="Admin",
            prenom="Super",
        )
        db.add(admin)
        db.flush()
        uo = UserOrganisation(
            id=uuid.uuid4(),
            user_id=admin.id,
            organisation_id=org.id,
            role=RoleEnum.admin,
        )
        db.add(uo)
        print(f"Admin créé : {admin.email} / admin1234")
    else:
        print("Admin déjà existant.")

    # Langues
    for code, nom in [("fr", "Français"), ("en", "English")]:
        if not db.query(Language).filter(Language.code == code).first():
            db.add(Language(id=uuid.uuid4(), code=code, nom=nom))
            print(f"Langue ajoutée : {nom}")

    db.commit()
    db.close()
    print("\nDone ! Lance l'application avec : uvicorn main:app --reload")

if __name__ == "__main__":
    seed()
