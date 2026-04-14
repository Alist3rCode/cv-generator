"""
routers/profile.py — Dashboard + formulaire de profil complet (avec bio multi-langue)
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Language, Bio, Experience, Formation, Competence, Certification
from routers.auth import require_user

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="templates")


def compute_completion(user_id, db: Session) -> tuple[int, dict]:
    """Calcule le % de complétion du profil (4 critères = 25% chacun)."""
    criteria = {
        "bio":        db.query(Bio).filter(Bio.user_id == user_id).count() > 0,
        "experience": db.query(Experience).filter(Experience.user_id == user_id).count() > 0,
        "formation":  db.query(Formation).filter(Formation.user_id == user_id).count() > 0,
        "competence": db.query(Competence).filter(Competence.user_id == user_id).count() > 0,
    }
    completed = sum(1 for v in criteria.values() if v)
    return int(completed / len(criteria) * 100), criteria


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    completion, criteria = compute_completion(current_user.id, db)

    # Donnees pour le resume CV
    languages     = db.query(Language).all()
    default_lang  = languages[0] if languages else None

    bio = None
    if default_lang:
        bio = db.query(Bio).filter(
            Bio.user_id == current_user.id,
            Bio.language_id == default_lang.id,
        ).first()

    all_exps   = db.query(Experience).filter(Experience.user_id == current_user.id).order_by(Experience.date_debut.desc()).all()
    all_forms  = db.query(Formation).filter(Formation.user_id == current_user.id).order_by(Formation.date_debut.desc()).all()
    all_certs  = db.query(Certification).filter(Certification.user_id == current_user.id).order_by(Certification.date_obtention.desc()).all()

    def _dedup(items):
        seen, result = set(), []
        for item in items:
            if item.gid not in seen:
                seen.add(item.gid)
                result.append(item)
        return result

    return templates.TemplateResponse("profile/dashboard.html", {
        "request":      request,
        "current_user": current_user,
        "completion":   completion,
        "criteria":     criteria,
        "bio":          bio,
        "experiences":  _dedup(all_exps),
        "formations":   _dedup(all_forms),
        "certifications": _dedup(all_certs),
    })


@router.get("/profile/edit", response_class=HTMLResponse)
def edit_profile_page(
    request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    profile   = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    languages = db.query(Language).all()

    # Langue active
    active_language = languages[0] if languages else None
    if language_id:
        found = db.query(Language).filter(Language.id == uuid.UUID(language_id)).first()
        if found:
            active_language = found

    # Bio pour la langue active
    bio = None
    if active_language:
        bio = db.query(Bio).filter(
            Bio.user_id == current_user.id,
            Bio.language_id == active_language.id,
        ).first()

    # Quelles langues ont déjà une bio sauvegardée (dict pour la macro lang_tabs)
    bios_by_lang = {
        str(b.language_id): b
        for b in db.query(Bio).filter(Bio.user_id == current_user.id).all()
    }

    return templates.TemplateResponse("profile/edit.html", {
        "request":         request,
        "current_user":    current_user,
        "profile":         profile,
        "languages":       languages,
        "active_language": active_language,
        "bio":             bio,
        "bios_by_lang":    bios_by_lang,
    })


@router.post("/profile/edit")
def edit_profile(
    request: Request,
    telephone: Optional[str]    = Form(None),
    linkedin_url: Optional[str] = Form(None),
    bio_texte: Optional[str]    = Form(None),
    language_id: Optional[str]  = Form(None),
    db: Session                 = Depends(get_db),
    current_user: User          = Depends(require_user),
):
    # Sauvegarder le profil (téléphone, LinkedIn)
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        profile.telephone    = telephone or None
        profile.linkedin_url = linkedin_url or None
    else:
        profile = Profile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            telephone=telephone or None,
            linkedin_url=linkedin_url or None,
        )
        db.add(profile)

    # Sauvegarder la bio pour la langue active
    lang_id_str = (language_id or "").strip()
    if bio_texte is not None and lang_id_str:
        try:
            lang_uuid = uuid.UUID(lang_id_str)
        except ValueError:
            lang_uuid = None
        if lang_uuid:
            bio = db.query(Bio).filter(
                Bio.user_id == current_user.id,
                Bio.language_id == lang_uuid,
            ).first()
            if bio:
                if bio_texte.strip():
                    bio.texte = bio_texte
                else:
                    db.delete(bio)
            elif bio_texte.strip():
                bio = Bio(
                    id=uuid.uuid4(),
                    user_id=current_user.id,
                    language_id=lang_uuid,
                    texte=bio_texte,
                )
                db.add(bio)

    db.commit()
    redirect_lang = f"?language_id={language_id}" if language_id else ""
    return RedirectResponse(url=f"/profile/edit{redirect_lang}", status_code=303)
