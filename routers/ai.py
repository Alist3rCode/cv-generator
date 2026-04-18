"""
routers/ai.py — Fonctionnalités IA (import CV + traduction) via Gemini.
"""

import json
import logging
import os
import tempfile
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cv_generator.ai")

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import (
    AIConfig, Bio, Certification, Competence, Experience, Formation,
    Language, Profile, ProfilLangue, SkillLevelEnum, SkillTypeEnum,
    CEFRLevelEnum, User,
)
from routers.auth import require_user

router     = APIRouter(prefix="/ai", tags=["ai"])
templates  = Jinja2Templates(directory="templates")

ALLOWED_MIME = {
    "application/pdf": "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXT = {".pdf", ".docx"}


def _ai_enabled(db: Session) -> tuple[bool, str]:
    """Retourne (is_enabled, reason). Vérifie config DB puis env."""
    cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
    if cfg and cfg.is_active and cfg.api_key:
        return True, ""
    if os.getenv("GEMINI_API_KEY"):
        return True, ""
    return False, "L'IA n'est pas configurée. Contactez un administrateur."


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ── Page principale ────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def ai_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    languages  = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()
    enabled, reason = _ai_enabled(db)
    return templates.TemplateResponse("ai/index.html", {
        "request":      request,
        "current_user": current_user,
        "languages":    languages,
        "ai_enabled":   enabled,
        "ai_disabled_reason": reason,
    })


# ── Import CV — Preview ────────────────────────────────────────────────────


@router.post("/import/preview")
async def import_cv_preview(
    request: Request,
    file: UploadFile = File(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    from services.gemini import extract_cv_data

    enabled, reason = _ai_enabled(db)
    if not enabled:
        return JSONResponse({"error": reason}, status_code=400)

    # Vérifier l'extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        return JSONResponse({"error": f"Format non supporté ({ext}). Utilisez PDF ou DOCX."}, status_code=400)

    # Récupérer la langue
    try:
        lang = db.query(Language).filter(Language.id == uuid.UUID(language_id)).first()
    except (ValueError, Exception):
        lang = None
    if not lang:
        return JSONResponse({"error": "Langue invalide."}, status_code=400)

    # Sauvegarder le fichier en temp
    content   = await file.read()
    mime_type = ALLOWED_MIME.get(file.content_type or "", "application/octet-stream")
    if ext == ".pdf":
        mime_type = "application/pdf"
    elif ext == ".docx":
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        data = extract_cv_data(tmp_path, mime_type, lang.nom)
    except Exception as e:
        from services.gemini import GeminiRateLimitError
        if isinstance(e, GeminiRateLimitError):
            logger.warning("Gemini rate limit (import): %s", e)
            return JSONResponse({
                "error": str(e),
                "rate_limited": True,
                "retry_after": e.retry_after_seconds,
            }, status_code=429)
        logger.exception("Erreur import CV Gemini")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # ── Données existantes en DB (pour les infobulles et l'avertissement) ──
    uid       = current_user.id
    lang_uuid = uuid.UUID(language_id)
    existing: dict = {}

    profile = db.query(Profile).filter(Profile.user_id == uid).first()
    if profile:
        ep = {}
        if profile.telephone:    ep["telephone"]    = profile.telephone
        if profile.linkedin_url: ep["linkedin_url"] = profile.linkedin_url
        if profile.poste:        ep["poste"]        = profile.poste
        if ep:
            existing["profile"] = ep

    bio = db.query(Bio).filter(Bio.user_id == uid, Bio.language_id == lang_uuid).first()
    if bio and bio.texte:
        existing["bio"] = {"texte": bio.texte}

    langues = db.query(ProfilLangue).filter(ProfilLangue.user_id == uid).all()
    if langues:
        existing["profil_langues"] = [{"nom": l.nom, "niveau": l.niveau.value} for l in langues]

    exp_count  = db.query(Experience).filter(Experience.user_id == uid, Experience.deleted_at == None).count()
    form_count = db.query(Formation).filter(Formation.user_id == uid, Formation.deleted_at == None).count()
    cert_count = db.query(Certification).filter(Certification.user_id == uid, Certification.deleted_at == None).count()
    comp_count = db.query(Competence).filter(Competence.user_id == uid).count()
    if exp_count:  existing["experiences_count"]    = exp_count
    if form_count: existing["formations_count"]     = form_count
    if cert_count: existing["certifications_count"] = cert_count
    if comp_count: existing["competences_count"]    = comp_count

    has_existing = bool(existing)

    return JSONResponse({
        "status":        "ok",
        "data":          data,
        "language_id":   language_id,
        "language_nom":  lang.nom,
        "existing":      existing,
        "has_existing":  has_existing,
    })


# ── Import CV — Save ───────────────────────────────────────────────────────


@router.post("/import/save")
def import_cv_save(
    request: Request,
    data: str        = Form(...),   # JSON stringifié
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Données invalides."}, status_code=400)

    try:
        lang_uuid = uuid.UUID(language_id)
    except ValueError:
        return JSONResponse({"error": "Langue invalide."}, status_code=400)

    uid = current_user.id

    # 1. Profile
    prof_data = payload.get("profile") or {}
    profile   = db.query(Profile).filter(Profile.user_id == uid).first()
    if profile:
        profile.telephone    = prof_data.get("telephone") or profile.telephone
        profile.linkedin_url = prof_data.get("linkedin_url") or profile.linkedin_url
        profile.poste        = prof_data.get("poste") or profile.poste
    else:
        profile = Profile(
            id=uuid.uuid4(), user_id=uid,
            telephone=prof_data.get("telephone") or None,
            linkedin_url=prof_data.get("linkedin_url") or None,
            poste=prof_data.get("poste") or None,
        )
        db.add(profile)

    # 2. Bio
    bio_data = payload.get("bio") or {}
    bio_texte = (bio_data.get("texte") or "").strip()
    if bio_texte:
        bio = db.query(Bio).filter(Bio.user_id == uid, Bio.language_id == lang_uuid).first()
        if bio:
            bio.texte = bio_texte
        else:
            db.add(Bio(
                id=uuid.uuid4(), user_id=uid, language_id=lang_uuid,
                texte=bio_texte, poste=prof_data.get("poste") or None,
            ))

    # 3. Langues parlées — remplacer entièrement
    db.query(ProfilLangue).filter(ProfilLangue.user_id == uid).delete()
    for pl in (payload.get("profil_langues") or []):
        nom = (pl.get("nom") or "").strip()
        niv = (pl.get("niveau") or "").strip()
        if not nom or not niv:
            continue
        try:
            niveau_enum = CEFRLevelEnum(niv)
        except ValueError:
            niveau_enum = CEFRLevelEnum.B2
        db.add(ProfilLangue(id=uuid.uuid4(), user_id=uid, nom=nom, niveau=niveau_enum))

    # 4. Compétences — déduplique par nom
    comp_gid_by_nom: dict[str, uuid.UUID] = {}
    existing_comps = db.query(Competence).filter(Competence.user_id == uid, Competence.language_id == lang_uuid).all()
    for c in existing_comps:
        comp_gid_by_nom[c.nom.lower()] = c.gid

    def _upsert_competence(nom: str, skill_type: SkillTypeEnum, famille: str) -> Optional[uuid.UUID]:
        key = nom.strip().lower()
        if not key:
            return None
        if key in comp_gid_by_nom:
            return comp_gid_by_nom[key]
        new_gid = uuid.uuid4()
        db.add(Competence(
            id=uuid.uuid4(), gid=new_gid, user_id=uid, language_id=lang_uuid,
            nom=nom.strip(), type=skill_type,
            niveau=SkillLevelEnum.one,  # Débutant par défaut
            famille=(famille or "").strip() or None,
        ))
        comp_gid_by_nom[key] = new_gid
        return new_gid

    competences_data = payload.get("competences") or {}
    for item in (competences_data.get("hard") or []):
        _upsert_competence(item.get("nom", ""), SkillTypeEnum.hard, item.get("famille", ""))
    for item in (competences_data.get("soft") or []):
        _upsert_competence(item.get("nom", ""), SkillTypeEnum.soft, item.get("famille", ""))

    # 5. Expériences (sans lien compétences)
    for exp in (payload.get("experiences") or []):
        titre = (exp.get("titre_poste") or "").strip()
        entreprise = (exp.get("entreprise") or "").strip()
        if not titre or not entreprise:
            continue
        # date_debut obligatoire en base — fallback au 01/01 de l'année courante si absent
        d_debut = _parse_date(exp.get("date_debut")) or date(date.today().year, 1, 1)
        db.add(Experience(
            id=uuid.uuid4(), gid=uuid.uuid4(), user_id=uid, language_id=lang_uuid,
            titre_poste=titre, entreprise=entreprise,
            location=(exp.get("location") or None),
            date_debut=d_debut, date_fin=_parse_date(exp.get("date_fin")),
            project_summary=(exp.get("project_summary") or None),
            description=(exp.get("description") or None),
            hard_skills=None, soft_skills=None,
        ))

    # 6. Formations
    for form in (payload.get("formations") or []):
        diplome = (form.get("diplome") or "").strip()
        etab    = (form.get("etablissement") or "").strip()
        if not diplome or not etab:
            continue
        # date_debut obligatoire en base — fallback au 01/01 de l'année courante si absent
        d_debut = _parse_date(form.get("date_debut")) or date(date.today().year, 1, 1)
        db.add(Formation(
            id=uuid.uuid4(), gid=uuid.uuid4(), user_id=uid, language_id=lang_uuid,
            diplome=diplome, etablissement=etab,
            ville=(form.get("ville") or None),
            date_debut=d_debut, date_fin=_parse_date(form.get("date_fin")),
        ))

    # 7. Certifications
    for cert in (payload.get("certifications") or []):
        titre   = (cert.get("titre") or "").strip()
        organisme = (cert.get("organisme") or "").strip()
        d_obt   = _parse_date(cert.get("date_obtention"))
        if not titre or not organisme or not d_obt:
            continue
        db.add(Certification(
            id=uuid.uuid4(), gid=uuid.uuid4(), user_id=uid, language_id=lang_uuid,
            titre=titre, organisme=organisme,
            date_obtention=d_obt, date_fin=_parse_date(cert.get("date_fin")),
        ))

    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


# ── Traduction — Preview ───────────────────────────────────────────────────


@router.post("/translate/preview")
def translate_preview(
    request: Request,
    language_from_id: str   = Form(...),
    language_to_id: str     = Form(...),
    types: list[str]        = Form(default=[]),
    db: Session             = Depends(get_db),
    current_user: User      = Depends(require_user),
):
    from services.gemini import translate_cv_data

    enabled, reason = _ai_enabled(db)
    if not enabled:
        return JSONResponse({"error": reason}, status_code=400)

    try:
        lang_from_uuid = uuid.UUID(language_from_id)
        lang_to_uuid   = uuid.UUID(language_to_id)
    except ValueError:
        return JSONResponse({"error": "Langue invalide."}, status_code=400)

    lang_from = db.query(Language).filter(Language.id == lang_from_uuid).first()
    lang_to   = db.query(Language).filter(Language.id == lang_to_uuid).first()
    if not lang_from or not lang_to:
        return JSONResponse({"error": "Langue introuvable."}, status_code=400)

    uid = current_user.id
    payload: dict = {}

    if "bio" in types:
        bio = db.query(Bio).filter(Bio.user_id == uid, Bio.language_id == lang_from_uuid).first()
        if bio:
            payload["bio"] = {"texte": bio.texte or "", "poste": bio.poste or ""}

    if "experiences" in types:
        exps = db.query(Experience).filter(
            Experience.user_id == uid, Experience.language_id == lang_from_uuid,
            Experience.deleted_at == None,
        ).order_by(Experience.date_debut.desc()).all()
        payload["experiences"] = [
            {
                "_gid": str(e.gid),
                "titre_poste":    e.titre_poste,
                "entreprise":     e.entreprise,
                "location":       e.location or "",
                "project_summary": e.project_summary or "",
                "description":    e.description or "",
            }
            for e in exps
        ]

    if "formations" in types:
        forms = db.query(Formation).filter(
            Formation.user_id == uid, Formation.language_id == lang_from_uuid,
            Formation.deleted_at == None,
        ).all()
        payload["formations"] = [
            {
                "_gid":       str(f.gid),
                "diplome":    f.diplome,
                "etablissement": f.etablissement,
                "ville":      f.ville or "",
            }
            for f in forms
        ]

    if "certifications" in types:
        certs = db.query(Certification).filter(
            Certification.user_id == uid, Certification.language_id == lang_from_uuid,
            Certification.deleted_at == None,
        ).all()
        payload["certifications"] = [
            {
                "_gid":     str(c.gid),
                "titre":    c.titre,
                "organisme": c.organisme,
            }
            for c in certs
        ]

    if "competences" in types:
        comps = db.query(Competence).filter(
            Competence.user_id == uid, Competence.language_id == lang_from_uuid,
        ).all()
        payload["competences"] = [
            {
                "_gid":    str(c.gid),
                "_type":   c.type.value,
                "_niveau": c.niveau.value,
                "nom":     c.nom,
                "famille": c.famille or "",
            }
            for c in comps
        ]

    if not payload:
        return JSONResponse({"error": "Aucun contenu à traduire dans les types sélectionnés."}, status_code=400)

    try:
        translated = translate_cv_data(payload, lang_from.nom, lang_to.nom)
    except Exception as e:
        from services.gemini import GeminiRateLimitError
        if isinstance(e, GeminiRateLimitError):
            logger.warning("Gemini rate limit (traduction): %s", e)
            return JSONResponse({
                "error": str(e),
                "rate_limited": True,
                "retry_after": e.retry_after_seconds,
            }, status_code=429)
        logger.exception("Erreur traduction Gemini")
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({
        "status": "ok",
        "data": translated,
        "language_to_id": language_to_id,
        "language_to_nom": lang_to.nom,
        "source_payload": payload,  # pour afficher le texte original dans la modale
    })


# ── Traduction — Save ──────────────────────────────────────────────────────


@router.post("/translate/save")
def translate_save(
    request: Request,
    data: str          = Form(...),   # JSON stringifié
    language_to_id: str = Form(...),
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return JSONResponse({"error": "Données invalides."}, status_code=400)

    try:
        lang_uuid = uuid.UUID(language_to_id)
    except ValueError:
        return JSONResponse({"error": "Langue invalide."}, status_code=400)

    uid = current_user.id

    # Bio traduite
    bio_data = payload.get("bio")
    if bio_data:
        bio_texte = (bio_data.get("texte") or "").strip()
        bio_poste = (bio_data.get("poste") or "").strip()
        if bio_texte:
            bio = db.query(Bio).filter(Bio.user_id == uid, Bio.language_id == lang_uuid).first()
            if bio:
                bio.texte = bio_texte
                bio.poste = bio_poste or bio.poste
            else:
                db.add(Bio(
                    id=uuid.uuid4(), user_id=uid, language_id=lang_uuid,
                    texte=bio_texte, poste=bio_poste or None,
                ))

    # Expériences traduites
    for exp in (payload.get("experiences") or []):
        gid_str = exp.get("_gid", "")
        titre   = (exp.get("titre_poste") or "").strip()
        if not gid_str or not titre:
            continue
        try:
            gid_uuid = uuid.UUID(gid_str)
        except ValueError:
            continue
        # Récupérer l'original pour préserver les dates/location
        original = db.query(Experience).filter(
            Experience.gid == gid_uuid, Experience.user_id == uid,
        ).first()
        existing = db.query(Experience).filter(
            Experience.gid == gid_uuid, Experience.language_id == lang_uuid,
            Experience.user_id == uid,
        ).first()
        if existing:
            existing.titre_poste    = titre
            existing.entreprise     = exp.get("entreprise") or existing.entreprise
            existing.location       = exp.get("location") or existing.location
            existing.project_summary = exp.get("project_summary") or None
            existing.description    = exp.get("description") or None
        elif original:
            db.add(Experience(
                id=uuid.uuid4(), gid=gid_uuid, user_id=uid, language_id=lang_uuid,
                titre_poste=titre,
                entreprise=exp.get("entreprise") or original.entreprise,
                location=exp.get("location") or original.location,
                date_debut=original.date_debut, date_fin=original.date_fin,
                project_summary=exp.get("project_summary") or None,
                description=exp.get("description") or None,
                hard_skills=None, soft_skills=None,
            ))

    # Formations traduites
    for form in (payload.get("formations") or []):
        gid_str = form.get("_gid", "")
        diplome = (form.get("diplome") or "").strip()
        if not gid_str or not diplome:
            continue
        try:
            gid_uuid = uuid.UUID(gid_str)
        except ValueError:
            continue
        original = db.query(Formation).filter(Formation.gid == gid_uuid, Formation.user_id == uid).first()
        existing = db.query(Formation).filter(Formation.gid == gid_uuid, Formation.language_id == lang_uuid, Formation.user_id == uid).first()
        if existing:
            existing.diplome       = diplome
            existing.etablissement = form.get("etablissement") or existing.etablissement
            existing.ville         = form.get("ville") or existing.ville
        elif original:
            db.add(Formation(
                id=uuid.uuid4(), gid=gid_uuid, user_id=uid, language_id=lang_uuid,
                diplome=diplome,
                etablissement=form.get("etablissement") or original.etablissement,
                ville=form.get("ville") or original.ville,
                date_debut=original.date_debut, date_fin=original.date_fin,
            ))

    # Certifications traduites
    for cert in (payload.get("certifications") or []):
        gid_str = cert.get("_gid", "")
        titre   = (cert.get("titre") or "").strip()
        if not gid_str or not titre:
            continue
        try:
            gid_uuid = uuid.UUID(gid_str)
        except ValueError:
            continue
        original = db.query(Certification).filter(Certification.gid == gid_uuid, Certification.user_id == uid).first()
        existing = db.query(Certification).filter(Certification.gid == gid_uuid, Certification.language_id == lang_uuid, Certification.user_id == uid).first()
        if existing:
            existing.titre    = titre
            existing.organisme = cert.get("organisme") or existing.organisme
        elif original:
            db.add(Certification(
                id=uuid.uuid4(), gid=gid_uuid, user_id=uid, language_id=lang_uuid,
                titre=titre,
                organisme=cert.get("organisme") or original.organisme,
                date_obtention=original.date_obtention, date_fin=original.date_fin,
            ))

    # Compétences traduites
    for comp in (payload.get("competences") or []):
        gid_str = comp.get("_gid", "")
        nom     = (comp.get("nom") or "").strip()
        if not gid_str or not nom:
            continue
        try:
            gid_uuid = uuid.UUID(gid_str)
        except ValueError:
            continue
        original = db.query(Competence).filter(Competence.gid == gid_uuid, Competence.user_id == uid).first()
        existing = db.query(Competence).filter(Competence.gid == gid_uuid, Competence.language_id == lang_uuid, Competence.user_id == uid).first()
        if existing:
            existing.nom     = nom
            existing.famille = comp.get("famille") or existing.famille
        elif original:
            db.add(Competence(
                id=uuid.uuid4(), gid=gid_uuid, user_id=uid, language_id=lang_uuid,
                nom=nom, type=original.type, niveau=original.niveau,
                famille=comp.get("famille") or original.famille,
            ))

    db.commit()
    return RedirectResponse(url="/ai/", status_code=303)
