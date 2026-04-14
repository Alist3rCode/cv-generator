"""
routers/experiences.py — CRUD expériences professionnelles (multi-langue via GID)
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Experience, Language
from routers.auth import require_user

router = APIRouter(prefix="/experiences", tags=["experiences"])
templates = Jinja2Templates(directory="templates")


def _dedup_by_gid(items):
    """Retourne un item par GID (le premier rencontré)."""
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


@router.get("/", response_class=HTMLResponse)
def list_experiences(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_exps  = db.query(Experience).filter(Experience.user_id == current_user.id).order_by(Experience.date_debut.desc()).all()
    experiences = _dedup_by_gid(all_exps)
    if not experiences:
        return RedirectResponse(url="/experiences/new", status_code=302)
    languages   = db.query(Language).all()
    # Langues disponibles par GID
    langs_by_gid = {}
    for exp in all_exps:
        gid = str(exp.gid)
        langs_by_gid.setdefault(gid, set()).add(str(exp.language_id))
    return templates.TemplateResponse("experiences/list.html", {
        "request": request, "current_user": current_user,
        "experiences": experiences, "languages": languages,
        "langs_by_gid": langs_by_gid,
    })


@router.get("/new", response_class=HTMLResponse)
def new_experience_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("experiences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "exp": None, "gid": None,
        "active_language_id": str(languages[0].id) if languages else None,
        "translations_by_lang": {}, "source_id": None,
    })


@router.post("/new")
def create_experience(
    titre_poste: str          = Form(...),
    entreprise: str           = Form(...),
    location: Optional[str]   = Form(None),
    date_debut: date          = Form(...),
    date_fin: Optional[date]  = Form(None),
    project_summary: Optional[str] = Form(None),
    description: Optional[str]    = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    exp = Experience(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        titre_poste=titre_poste, entreprise=entreprise,
        location=location or None, date_debut=date_debut, date_fin=date_fin,
        project_summary=project_summary or None, description=description or None,
    )
    db.add(exp)
    db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.get("/{exp_id}/edit", response_class=HTMLResponse)
def edit_experience_page(
    exp_id: str, request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/experiences/", status_code=303)

    languages = db.query(Language).all()

    # Toutes les traductions du même GID
    translations = db.query(Experience).filter(
        Experience.gid == source.gid, Experience.user_id == current_user.id
    ).all()
    translations_by_lang = {str(t.language_id): t for t in translations}

    # Langue active
    active_lang_id = language_id or str(source.language_id)
    exp = translations_by_lang.get(active_lang_id, None)

    return templates.TemplateResponse("experiences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "exp": exp, "source": source,
        "gid": str(source.gid), "source_id": exp_id,
        "active_language_id": active_lang_id,
        "translations_by_lang": translations_by_lang,
    })


@router.post("/{exp_id}/edit")
def update_experience(
    exp_id: str,
    titre_poste: str          = Form(...),
    entreprise: str           = Form(...),
    location: Optional[str]   = Form(None),
    date_debut: date          = Form(...),
    date_fin: Optional[date]  = Form(None),
    project_summary: Optional[str] = Form(None),
    description: Optional[str]    = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/experiences/", status_code=303)

    lang_uuid = uuid.UUID(language_id)
    existing = db.query(Experience).filter(
        Experience.gid == source.gid, Experience.user_id == current_user.id,
        Experience.language_id == lang_uuid,
    ).first()

    if existing:
        existing.titre_poste = titre_poste; existing.entreprise = entreprise
        existing.location = location or None; existing.date_debut = date_debut
        existing.date_fin = date_fin; existing.project_summary = project_summary or None
        existing.description = description or None
    else:
        db.add(Experience(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, titre_poste=titre_poste, entreprise=entreprise,
            location=location or None, date_debut=date_debut, date_fin=date_fin,
            project_summary=project_summary or None, description=description or None,
        ))
    db.commit()
    return RedirectResponse(url=f"/experiences/{exp_id}/edit?language_id={language_id}", status_code=303)


@router.post("/{exp_id}/delete")
def delete_experience(exp_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    # Supprime toutes les traductions du même GID
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if source:
        db.query(Experience).filter(
            Experience.gid == source.gid, Experience.user_id == current_user.id
        ).delete()
        db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)
