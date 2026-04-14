"""
schemas.py — Pydantic v2 schemas (FastAPI)
CV Generator App

Convention de nommage :
  - XxxBase     : champs communs (pas d'id, pas d'audit)
  - XxxCreate   : payload POST (ce que le client envoie)
  - XxxUpdate   : payload PATCH (tous les champs optionnels)
  - XxxRead     : réponse API (id + audit inclus)
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


# ──────────────────────────────────────────────
# Enums (miroir des SQLAlchemy Enums)
# ──────────────────────────────────────────────

class RoleEnum(str, Enum):
    admin = "admin"
    user  = "user"


class SkillTypeEnum(str, Enum):
    hard = "hard"
    soft = "soft"


class SkillLevelEnum(int, Enum):
    debutant       = 1
    intermediaire  = 2
    avance         = 3
    expert         = 4


class ExportFormatEnum(str, Enum):
    docx = "docx"
    pdf  = "pdf"


# ──────────────────────────────────────────────
# Mixin : champs d'audit en lecture
# ──────────────────────────────────────────────

class AuditRead(BaseModel):
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None


# ──────────────────────────────────────────────
# Language
# ──────────────────────────────────────────────

class LanguageBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=5, examples=["fr", "en"])
    nom:  str = Field(..., max_length=50, examples=["Français", "English"])


class LanguageCreate(LanguageBase):
    pass


class LanguageUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=5)
    nom:  Optional[str] = Field(None, max_length=50)


class LanguageRead(LanguageBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)

    id:       UUID
    flag_url: str = ""

    @classmethod
    def from_orm_with_flag(cls, obj) -> "LanguageRead":
        instance = cls.model_validate(obj)
        instance.flag_url = f"https://flagcdn.com/{obj.code}.svg"
        return instance


# ──────────────────────────────────────────────
# Organisation
# ──────────────────────────────────────────────

class OrganisationBase(BaseModel):
    nom:       str            = Field(..., max_length=150)
    adresse:   Optional[str]  = None
    email:     Optional[EmailStr] = None
    telephone: Optional[str]  = Field(None, max_length=30)


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationUpdate(BaseModel):
    nom:       Optional[str]      = None
    adresse:   Optional[str]      = None
    email:     Optional[EmailStr] = None
    telephone: Optional[str]      = None


class OrganisationRead(OrganisationBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


# ──────────────────────────────────────────────
# User
# ──────────────────────────────────────────────

class UserBase(BaseModel):
    email:  EmailStr
    nom:    str = Field(..., max_length=100)
    prenom: str = Field(..., max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email:    Optional[EmailStr] = None
    nom:      Optional[str]      = None
    prenom:   Optional[str]      = None
    password: Optional[str]      = Field(None, min_length=8)


class UserRead(UserBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    # password_hash volontairement absent


# ──────────────────────────────────────────────
# UserOrganisation
# ──────────────────────────────────────────────

class UserOrganisationBase(BaseModel):
    user_id:         UUID
    organisation_id: UUID
    role:            RoleEnum = RoleEnum.user


class UserOrganisationCreate(UserOrganisationBase):
    pass


class UserOrganisationUpdate(BaseModel):
    role: Optional[RoleEnum] = None


class UserOrganisationRead(UserOrganisationBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:           UUID
    user:         Optional[UserRead]         = None
    organisation: Optional[OrganisationRead] = None


# ──────────────────────────────────────────────
# Profile
# ──────────────────────────────────────────────

class ProfileBase(BaseModel):
    photo_url:    Optional[str] = Field(None, max_length=500)
    telephone:    Optional[str] = Field(None, max_length=30)
    linkedin_url: Optional[str] = Field(None, max_length=500)


class ProfileCreate(ProfileBase):
    user_id: UUID


class ProfileUpdate(ProfileBase):
    pass


class ProfileRead(ProfileBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:      UUID
    user_id: UUID


# ──────────────────────────────────────────────
# Bio
# ──────────────────────────────────────────────

class BioBase(BaseModel):
    texte: str


class BioCreate(BioBase):
    user_id:     UUID
    language_id: UUID


class BioUpdate(BaseModel):
    texte: Optional[str] = None


class BioRead(BioBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:          UUID
    user_id:     UUID
    language_id: UUID


# ──────────────────────────────────────────────
# Expérience
# ──────────────────────────────────────────────

class ExperienceBase(BaseModel):
    titre_poste:     str            = Field(..., max_length=200)
    entreprise:      str            = Field(..., max_length=200)
    location:        Optional[str]  = Field(None, max_length=200)
    date_debut:      date
    date_fin:        Optional[date] = None          # NULL = poste actuel
    project_summary: Optional[str]  = None
    description:     Optional[str]  = None
    hard_skills:     Optional[List[UUID]] = None    # GIDs de Competence
    soft_skills:     Optional[List[UUID]] = None


class ExperienceCreate(ExperienceBase):
    user_id:     UUID
    language_id: UUID
    gid:         Optional[UUID] = None  # fourni si c'est une traduction d'un item existant


class ExperienceUpdate(BaseModel):
    titre_poste:     Optional[str]        = None
    entreprise:      Optional[str]        = None
    location:        Optional[str]        = None
    date_debut:      Optional[date]       = None
    date_fin:        Optional[date]       = None
    project_summary: Optional[str]        = None
    description:     Optional[str]        = None
    hard_skills:     Optional[List[UUID]] = None
    soft_skills:     Optional[List[UUID]] = None


class ExperienceRead(ExperienceBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:          UUID
    gid:         UUID
    user_id:     UUID
    language_id: UUID


# ──────────────────────────────────────────────
# Formation
# ──────────────────────────────────────────────

class FormationBase(BaseModel):
    diplome:       str            = Field(..., max_length=200)
    etablissement: str            = Field(..., max_length=200)
    date_debut:    date
    date_fin:      Optional[date] = None
    description:   Optional[str]  = None


class FormationCreate(FormationBase):
    user_id:     UUID
    language_id: UUID
    gid:         Optional[UUID] = None


class FormationUpdate(BaseModel):
    diplome:       Optional[str]  = None
    etablissement: Optional[str]  = None
    date_debut:    Optional[date] = None
    date_fin:      Optional[date] = None
    description:   Optional[str]  = None


class FormationRead(FormationBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:          UUID
    gid:         UUID
    user_id:     UUID
    language_id: UUID


# ──────────────────────────────────────────────
# Certification
# ──────────────────────────────────────────────

class CertificationBase(BaseModel):
    titre:          str            = Field(..., max_length=200)
    organisme:      str            = Field(..., max_length=200)
    date_obtention: date
    date_fin:       Optional[date] = None   # NULL = pas d'expiration


class CertificationCreate(CertificationBase):
    user_id:     UUID
    language_id: UUID
    gid:         Optional[UUID] = None


class CertificationUpdate(BaseModel):
    titre:          Optional[str]  = None
    organisme:      Optional[str]  = None
    date_obtention: Optional[date] = None
    date_fin:       Optional[date] = None


class CertificationRead(CertificationBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:          UUID
    gid:         UUID
    user_id:     UUID
    language_id: UUID


# ──────────────────────────────────────────────
# Compétence
# ──────────────────────────────────────────────

class CompetenceBase(BaseModel):
    nom:    str            = Field(..., max_length=150)
    type:   SkillTypeEnum
    niveau: SkillLevelEnum


class CompetenceCreate(CompetenceBase):
    user_id:     UUID
    language_id: UUID
    gid:         Optional[UUID] = None


class CompetenceUpdate(BaseModel):
    nom:    Optional[str]            = None
    type:   Optional[SkillTypeEnum]  = None
    niveau: Optional[SkillLevelEnum] = None


class CompetenceRead(CompetenceBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:          UUID
    gid:         UUID
    user_id:     UUID
    language_id: UUID


# ──────────────────────────────────────────────
# Template
# ──────────────────────────────────────────────

class TemplateBase(BaseModel):
    nom:       str  = Field(..., max_length=150)
    is_active: bool = True


class TemplateCreate(TemplateBase):
    organisation_id: UUID
    # fichier_path est renseigné après l'upload du fichier, pas par le client


class TemplateUpdate(BaseModel):
    nom:       Optional[str]  = None
    is_active: Optional[bool] = None


class TemplateRead(TemplateBase, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:              UUID
    fichier_path:    str
    organisation_id: UUID
    uploaded_by:     UUID


# ──────────────────────────────────────────────
# CVExport
# ──────────────────────────────────────────────

class CVExportCreate(BaseModel):
    user_id:     UUID
    template_id: UUID
    language_id: UUID
    format:      ExportFormatEnum


class CVExportRead(CVExportCreate, AuditRead):
    model_config = ConfigDict(from_attributes=True)
    id:           UUID
    fichier_path: Optional[str]   = None    # NULL tant que la génération est en cours
    generated_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# Schémas composites (vues enrichies)
# ──────────────────────────────────────────────

class UserProfileRead(BaseModel):
    """Vue complète d'un user avec son profil non-traduisible."""
    model_config = ConfigDict(from_attributes=True)
    user:    UserRead
    profile: Optional[ProfileRead] = None


class FullProfileRead(BaseModel):
    """
    Vue complète d'un profil dans une langue donnée.
    Utilisé pour l'aperçu CV et la génération d'export.
    """
    user:           UserRead
    profile:        Optional[ProfileRead]       = None
    bio:            Optional[BioRead]           = None
    experiences:    List[ExperienceRead]        = []
    formations:     List[FormationRead]         = []
    certifications: List[CertificationRead]     = []
    competences:    List[CompetenceRead]        = []
    language:       Optional[LanguageRead]      = None
