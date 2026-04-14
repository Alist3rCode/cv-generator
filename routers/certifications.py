"""
routers/certifications.py — CRUD certifications (multi-langue via GID)
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Certification, Language
from routers.auth import require_user

router = APIRouter(prefix="/certifications", tags=["certifications"])

def _parse_date(value):
    """Convertit une chaine ISO en date, retourne None si vide."""
    from datetime import date as _date
    return _date.fromisoformat(value) if value and value.strip() else None

templates = Jinja2Templates(directory="templates")


def _dedup_by_gid(items):
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


@router.get("/", response_class=HTMLResponse)
def list_certifications(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_items = db.query(Certification).filter(Certification.user_id == current_user.id).order_by(Certification.date_obtention.desc()).all()
    certs     = _dedup_by_gid(all_items)
    if not certs:
        return RedirectResponse(url="/certifications/new", status_code=302)
    languages = db.query(Language).all()
    langs_by_gid = {}
    for c in all_items:
        langs_by_gid.setdefault(str(c.gid), set()).add(str(c.language_id))
    return templates.TemplateResponse("certifications/list.html", {
        "request": request, "current_user": current_user,
        "certifications": certs, "languages": languages, "langs_by_gid": langs_by_gid,
    })


@router.get("/new", response_class=HTMLResponse)
def new_certification_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("certifications/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "cert": None, "gid": None,
        "active_language_id": str(languages[0].id) if languages else None,
        "translations_by_lang": {}, "source_id": None,
    })


@router.post("/new")
def create_certification(
    titre: str                = Form(...),
    organisme: str            = Form(...),
    date_obtention: str       = Form(...),
    date_fin: Optional[str]   = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    db.add(Certification(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id), titre=titre,
        organisme=organisme, date_obtention=_parse_date(date_obtention), date_fin=_parse_date(date_fin),
    ))
    db.commit()
    return RedirectResponse(url="/certifications/", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_certification_page(
    cid: str, request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Certification).filter(
        Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/certifications/", status_code=303)

    languages = db.query(Language).all()
    translations = db.query(Certification).filter(
        Certification.gid == source.gid, Certification.user_id == current_user.id
    ).all()
    translations_by_lang = {str(t.language_id): t for t in translations}
    active_lang_id = language_id or str(source.language_id)
    cert = translations_by_lang.get(active_lang_id, None)

    return templates.TemplateResponse("certifications/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "cert": cert, "source": source,
        "gid": str(source.gid), "source_id": cid,
        "active_language_id": active_lang_id,
        "translations_by_lang": translations_by_lang,
    })


@router.post("/{cid}/edit")
def update_certification(
    cid: str,
    titre: str                = Form(...),
    organisme: str            = Form(...),
    date_obtention: str       = Form(...),
    date_fin: Optional[str]   = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    source = db.query(Certification).filter(
        Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/certifications/", status_code=303)

    lang_uuid = uuid.UUID(language_id)
    existing = db.query(Certification).filter(
        Certification.gid == source.gid, Certification.user_id == current_user.id,
        Certification.language_id == lang_uuid,
    ).first()

    if existing:
        existing.titre = titre; existing.organisme = organisme
        existing.date_obtention = _parse_date(date_obtention); existing.date_fin = _parse_date(date_fin)
    else:
        db.add(Certification(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, titre=titre, organisme=organisme,
            date_obtention=_parse_date(date_obtention), date_fin=_parse_date(date_fin),
        ))
    db.commit()
    return RedirectResponse(url=f"/certifications/{cid}/edit?language_id={language_id}", status_code=303)


@router.post("/{cid}/delete")
def delete_certification(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    source = db.query(Certification).filter(
        Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id
    ).first()
    if source:
        db.query(Certification).filter(
            Certification.gid == source.gid, Certification.user_id == current_user.id
        ).delete()
        db.commit()
    return RedirectResponse(url="/certifications/", status_code=303)
