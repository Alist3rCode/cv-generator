"""
models.py — SQLAlchemy ORM models
CV Generator App
"""

import uuid
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import Uuid


# ──────────────────────────────────────────────
# Base & Mixins
# ──────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class AuditMixin:
    """Champs d'audit présents sur toutes les tables."""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Uuid, ForeignKey("user.id"), nullable=True)
    updated_by = Column(Uuid, ForeignKey("user.id"), nullable=True)


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class RoleEnum(PyEnum):
    admin = "admin"
    user  = "user"


class SkillTypeEnum(PyEnum):
    hard = "hard"
    soft = "soft"


class SkillLevelEnum(PyEnum):
    one   = 1  # Débutant
    two   = 2  # Intermédiaire
    three = 3  # Avancé
    four  = 4  # Expert


class ExportFormatEnum(PyEnum):
    docx = "docx"
    pdf  = "pdf"


class CEFRLevelEnum(PyEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

CEFR_LABELS = {
    "A1": "A1 — Débutant",
    "A2": "A2 — Élémentaire",
    "B1": "B1 — Intermédiaire",
    "B2": "B2 — Intermédiaire avancé",
    "C1": "C1 — Autonome",
    "C2": "C2 — Maîtrise",
}


# ──────────────────────────────────────────────
# Paramétrage
# ──────────────────────────────────────────────

class Language(AuditMixin, Base):
    """
    Langues supportées par l'application.
    Le drapeau est construit dynamiquement côté front :
    https://flagcdn.com/{code}.svg
    """
    __tablename__ = "language"

    id   = Column(Uuid, primary_key=True, default=uuid.uuid4)
    code = Column(String(5),  nullable=False, unique=True)   # 'fr', 'en', 'es'...
    nom  = Column(String(50), nullable=False)                 # 'Français', 'English'...

    # Relations
    bios           = relationship("Bio",           back_populates="language")
    experiences    = relationship("Experience",    back_populates="language")
    formations     = relationship("Formation",     back_populates="language")
    certifications = relationship("Certification", back_populates="language")
    competences    = relationship("Competence",    back_populates="language")
    cv_exports     = relationship("CVExport",      back_populates="language")


# ──────────────────────────────────────────────
# Organisation & Users
# ──────────────────────────────────────────────

class Organisation(AuditMixin, Base):
    __tablename__ = "organisation"

    id        = Column(Uuid, primary_key=True, default=uuid.uuid4)
    nom       = Column(String(150), nullable=False)
    adresse   = Column(Text,        nullable=True)
    email     = Column(String(150), nullable=True)
    telephone = Column(String(30),  nullable=True)

    # Relations
    user_organisations = relationship("UserOrganisation", back_populates="organisation")
    templates          = relationship("Template",         back_populates="organisation")


class User(AuditMixin, Base):
    __tablename__ = "user"

    id            = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email         = Column(String(150), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    nom           = Column(String(100), nullable=False)
    prenom        = Column(String(100), nullable=False)

    # Relations
    user_organisations = relationship("UserOrganisation", back_populates="user",
                                      foreign_keys="UserOrganisation.user_id")
    profile            = relationship("Profile",          back_populates="user", uselist=False,
                                      foreign_keys="Profile.user_id")
    bios               = relationship("Bio",              back_populates="user",
                                      foreign_keys="Bio.user_id")
    experiences        = relationship("Experience",       back_populates="user",
                                      foreign_keys="Experience.user_id")
    formations         = relationship("Formation",        back_populates="user",
                                      foreign_keys="Formation.user_id")
    certifications     = relationship("Certification",    back_populates="user",
                                      foreign_keys="Certification.user_id")
    competences        = relationship("Competence",       back_populates="user",
                                      foreign_keys="Competence.user_id")
    cv_exports         = relationship("CVExport",         back_populates="user",
                                      foreign_keys="CVExport.user_id")
    profil_langues     = relationship("ProfilLangue",     back_populates="user",
                                      foreign_keys="ProfilLangue.user_id")


class UserOrganisation(AuditMixin, Base):
    """Table de jonction User ↔ Organisation avec rôle."""
    __tablename__ = "user_organisation"
    __table_args__ = (
        UniqueConstraint("user_id", "organisation_id", name="uq_user_organisation"),
    )

    id              = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id         = Column(Uuid, ForeignKey("user.id"),         nullable=False)
    organisation_id = Column(Uuid, ForeignKey("organisation.id"), nullable=False)
    role            = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.user)

    # Relations
    user         = relationship("User",         back_populates="user_organisations",
                                foreign_keys=[user_id])
    organisation = relationship("Organisation", back_populates="user_organisations")


# ──────────────────────────────────────────────
# Profil (données non-traduisibles)
# ──────────────────────────────────────────────

class Profile(AuditMixin, Base):
    """Données fixes du user, indépendantes de la langue."""
    __tablename__ = "profile"

    id           = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id      = Column(Uuid, ForeignKey("user.id"), nullable=False, unique=True)
    photo_url    = Column(String(500), nullable=True)
    telephone    = Column(String(30),  nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    poste        = Column(String(200), nullable=True)

    # Relations
    user = relationship("User", back_populates="profile", foreign_keys=[user_id])


# ──────────────────────────────────────────────
# Langues parlées (profil utilisateur)
# ──────────────────────────────────────────────

class ProfilLangue(AuditMixin, Base):
    """Langues parlées par l'utilisateur, avec niveau CEFR."""
    __tablename__ = "profil_langue"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("user.id"), nullable=False)
    nom     = Column(String(100), nullable=False)   # ex: "Anglais", "Espagnol"
    niveau  = Column(Enum(CEFRLevelEnum), nullable=False)

    # Relations
    user = relationship("User", back_populates="profil_langues", foreign_keys=[user_id])


# ──────────────────────────────────────────────
# Tables traduisibles — Mixin GID
# ──────────────────────────────────────────────

class TranslatableMixin:
    """
    Mixin pour toutes les tables avec support multi-langue.
    Le GID (Group ID) regroupe toutes les traductions d'un même élément.
    """
    gid         = Column(Uuid, nullable=False, default=uuid.uuid4, index=True)
    language_id = Column(Uuid, ForeignKey("language.id"), nullable=False)


# ──────────────────────────────────────────────
# Bio
# ──────────────────────────────────────────────

class Bio(AuditMixin, Base):
    """
    Une bio par user par langue. Pas de GID nécessaire —
    user_id + language_id est suffisant pour l'identifier.
    """
    __tablename__ = "bio"
    __table_args__ = (
        UniqueConstraint("user_id", "language_id", name="uq_bio_user_language"),
    )

    id          = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id     = Column(Uuid, ForeignKey("user.id"),     nullable=False)
    language_id = Column(Uuid, ForeignKey("language.id"), nullable=False)
    texte       = Column(Text, nullable=False)

    # Relations
    user     = relationship("User",     back_populates="bios",     foreign_keys=[user_id])
    language = relationship("Language", back_populates="bios")


# ──────────────────────────────────────────────
# Expérience
# ──────────────────────────────────────────────

class Experience(TranslatableMixin, AuditMixin, Base):
    """
    Expérience professionnelle.
    hard_skills / soft_skills : liste de GIDs (UUID str) pointant vers Competence.
    Tous les champs texte sont traduisibles, y compris entreprise et location.
    """
    __tablename__ = "experience"

    id              = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id         = Column(Uuid, ForeignKey("user.id"), nullable=False)
    titre_poste     = Column(String(200), nullable=False)
    entreprise      = Column(String(200), nullable=False)
    location        = Column(String(200), nullable=True)
    date_debut      = Column(Date,        nullable=False)
    date_fin        = Column(Date,        nullable=True)   # NULL = poste actuel
    project_summary = Column(Text,        nullable=True)
    description     = Column(Text,        nullable=True)
    hard_skills     = Column(JSON,        nullable=True)   # ["gid-uuid-1", "gid-uuid-2", ...]
    soft_skills     = Column(JSON,        nullable=True)   # ["gid-uuid-3", ...]
    deleted_at      = Column(DateTime,    nullable=True)   # NULL = actif

    # Relations
    user     = relationship("User",     back_populates="experiences", foreign_keys=[user_id])
    language = relationship("Language", back_populates="experiences")


# ──────────────────────────────────────────────
# Formation
# ──────────────────────────────────────────────

class Formation(TranslatableMixin, AuditMixin, Base):
    __tablename__ = "formation"

    id             = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id        = Column(Uuid, ForeignKey("user.id"), nullable=False)
    diplome        = Column(String(200), nullable=False)
    etablissement  = Column(String(200), nullable=False)
    ville          = Column(String(100), nullable=True)
    date_debut     = Column(Date,        nullable=False)
    date_fin       = Column(Date,        nullable=True)
    description    = Column(Text,        nullable=True)
    deleted_at     = Column(DateTime,    nullable=True)   # NULL = actif

    # Relations
    user     = relationship("User",     back_populates="formations", foreign_keys=[user_id])
    language = relationship("Language", back_populates="formations")


# ──────────────────────────────────────────────
# Certification
# ──────────────────────────────────────────────

class Certification(TranslatableMixin, AuditMixin, Base):
    __tablename__ = "certification"

    id              = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id         = Column(Uuid, ForeignKey("user.id"), nullable=False)
    titre           = Column(String(200), nullable=False)
    organisme       = Column(String(200), nullable=False)
    date_obtention  = Column(Date,        nullable=False)
    date_fin        = Column(Date,        nullable=True)   # NULL = pas d'expiration
    deleted_at      = Column(DateTime,    nullable=True)   # NULL = actif

    # Relations
    user     = relationship("User",     back_populates="certifications", foreign_keys=[user_id])
    language = relationship("Language", back_populates="certifications")


# ──────────────────────────────────────────────
# Compétence
# ──────────────────────────────────────────────

class Competence(TranslatableMixin, AuditMixin, Base):
    """
    niveau : 1=Débutant | 2=Intermédiaire | 3=Avancé | 4=Expert
    """
    __tablename__ = "competence"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("user.id"), nullable=False)
    nom     = Column(String(150), nullable=False)
    type    = Column(Enum(SkillTypeEnum),  nullable=False)
    niveau  = Column(Enum(SkillLevelEnum), nullable=False)
    famille = Column(String(150), nullable=True)   # Famille de compétence (à renseigner ultérieurement)

    # Relations
    user     = relationship("User",     back_populates="competences", foreign_keys=[user_id])
    language = relationship("Language", back_populates="competences")


# ──────────────────────────────────────────────
# Template Word
# ──────────────────────────────────────────────

class Template(AuditMixin, Base):
    """
    Template .docx uploadé par un admin, rattaché à une organisation.
    Un seul template actif par organisation à la fois (géré applicativement).
    """
    __tablename__ = "template"

    id              = Column(Uuid, primary_key=True, default=uuid.uuid4)
    nom             = Column(String(150), nullable=False)
    fichier_path    = Column(String(500), nullable=False)
    organisation_id = Column(Uuid, ForeignKey("organisation.id"), nullable=False)
    uploaded_by     = Column(Uuid, ForeignKey("user.id"),         nullable=False)
    is_active       = Column(Boolean, nullable=False, default=True)

    # Relations
    organisation = relationship("Organisation", back_populates="templates")
    cv_exports   = relationship("CVExport",     back_populates="template")


# ──────────────────────────────────────────────
# Export CV
# ──────────────────────────────────────────────

class CVExport(AuditMixin, Base):
    """
    Trace de chaque export généré.
    Permet de re-télécharger sans régénérer.
    """
    __tablename__ = "cv_export"

    id           = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id      = Column(Uuid, ForeignKey("user.id"),      nullable=False)
    template_id  = Column(Uuid, ForeignKey("template.id"),  nullable=False)
    language_id  = Column(Uuid, ForeignKey("language.id"),  nullable=False)
    format       = Column(Enum(ExportFormatEnum), nullable=False)
    nom          = Column(String(200), nullable=True)        # Nom personnalisé de l'export
    fichier_path = Column(String(500), nullable=True)   # NULL tant que la génération n'est pas terminée
    generated_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    user     = relationship("User",     back_populates="cv_exports", foreign_keys=[user_id])
    template = relationship("Template", back_populates="cv_exports")
    language = relationship("Language", back_populates="cv_exports")
