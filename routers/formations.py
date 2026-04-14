"""
routers/formations.py — CRUD formations (multi-langue via GID)
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Formation, Language
from routers.auth import require_user

router = APIRouter(prefix="/formations", tags=["formations"])
templates = Jinja2Templates(directory="templates")


def _dedup_by_gid(items):
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


@router.get("/", response_class=HTMLResponse)
def list_formations(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_items = db.query(Formation).filter(Formation.user_id == current_user.id).order_by(Formation.date_debut.desc()).all()
    formations = _dedup_by_gid(all_items)
    languages  = db.query(Language).all()
    langs_by_gid = {}
    for f in all_items:
        langs_by_gid.setdefault(str(f.gid), set()).add(str(f.language_id))
    return templates.TemplateResponse("formations/list.html", {
        "request": request, "current_user": current_user,
        "formations": formations, "languages": languages, "langs_by_gid": langs_by_gid,
    })


@router.get("/new", response_class=HTMLResponse)
def new_formation_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("formations/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "formation": None, "gid": None,
        "active_language_id": str(languages[0].id) if languages else None,
        "translations_by_lang": {}, "source_id": None,
    })


@router.post("/new")
def create_formation(
    diplome: str              = Form(...),
    etablissement: str        = Form(...),
    date_debut: date          = Form(...),
    date_fin: Optional[date]  = Form(None),
    description: Optional[str] = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    db.add(Formation(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id), diplome=diplome,
        etablissement=etablissement, date_debut=date_debut,
        date_fin=date_fin, description=description or None,
    ))
    db.commit()
    return RedirectResponse(url="/formations/", status_code=303)


@router.get("/{fid}/edit", response_class=HTMLResponse)
def edit_formation_page(
    fid: str, request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Formation).filter(
        Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/formations/", status_code=303)

    languages = db.query(Language).all()
    translations = db.query(Formation).filter(
        Formation.gid == source.gid, Formation.user_id == current_user.id
    ).all()
    translations_by_lang = {str(t.language_id): t for t in translations}
    active_lang_id = language_id or str(source.language_id)
    formation = translations_by_lang.get(active_lang_id, None)

    return templates.TemplateResponse("formations/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "formation": formation, "source": source,
        "gid": str(source.gid), "source_id": fid,
        "active_language_id": active_lang_id,
        "translations_by_lang": translations_by_lang,
    })


@router.post("/{fid}/edit")
def update_formation(
    fid: str,
    diplome: str              = Form(...),
    etablissement: str        = Form(...),
    date_debut: date          = Form(...),
    date_fin: Optional[date]  = Form(None),
    description: Optional[str] = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    source = db.query(Formation).filter(
        Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/formations/", status_code=303)

    lang_uuid = uuid.UUID(language_id)
    existing = db.query(Formation).filter(
        Formation.gid == source.gid, Formation.user_id == current_user.id,
        Formation.language_id == lang_uuid,
    ).first()

    if existing:
        existing.diplome = diplome; existing.etablissement = etablissement
        existing.date_debut = date_debut; existing.date_fin = date_fin
        existing.description = description or None
    else:
        db.add(Formation(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, diplome=diplome, etablissement=etablissement,
            date_debut=date_debut, date_fin=date_fin, description=description or None,
        ))
    db.commit()
    return RedirectResponse(url=f"/formations/{fid}/edit?language_id={language_id}", status_code=303)


@router.post("/{fid}/delete")
def delete_formation(fid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    source = db.query(Formation).filter(
        Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id
    ).first()
    if source:
        db.query(Formation).filter(
            Formation.gid == source.gid, Formation.user_id == current_user.id
        ).delete()
        db.commit()
    return RedirectResponse(url="/formations/", status_code=303)
