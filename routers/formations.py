"""
routers/formations.py — CRUD formations (multi-langue via GID)
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Formation, Language
from routers.auth import require_user

router = APIRouter(prefix="/formations", tags=["formations"])

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
def list_formations(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_items = db.query(Formation).filter(Formation.user_id == current_user.id, Formation.deleted_at == None).order_by(Formation.date_debut.desc()).all()
    formations = _dedup_by_gid(all_items)
    if not formations:
        return RedirectResponse(url="/formations/new", status_code=302)
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
    ville: Optional[str]      = Form(None),
    date_debut: str           = Form(...),
    date_fin: Optional[str]   = Form(None),
    description: Optional[str] = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    db.add(Formation(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id), diplome=diplome,
        etablissement=etablissement, ville=ville or None, date_debut=_parse_date(date_debut),
        date_fin=_parse_date(date_fin), description=description or None,
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
    request: Request,
    diplome: str              = Form(...),
    etablissement: str        = Form(...),
    ville: Optional[str]      = Form(None),
    date_debut: str           = Form(...),
    date_fin: Optional[str]   = Form(None),
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
        existing.ville = ville or None; existing.date_debut = _parse_date(date_debut); existing.date_fin = _parse_date(date_fin)
        existing.description = description or None
    else:
        db.add(Formation(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, diplome=diplome, etablissement=etablissement, ville=ville or None,
            date_debut=_parse_date(date_debut), date_fin=_parse_date(date_fin), description=description or None,
        ))
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": True})
    return RedirectResponse(url=f"/formations/{fid}/edit?language_id={language_id}", status_code=303)


@router.post("/{fid}/soft-delete")
def soft_delete_formation(fid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    from datetime import datetime as _dt
    source = db.query(Formation).filter(
        Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id
    ).first()
    if source:
        db.query(Formation).filter(
            Formation.gid == source.gid, Formation.user_id == current_user.id
        ).update({"deleted_at": _dt.utcnow()})
        db.commit()
    return RedirectResponse(url="/formations/", status_code=303)


@router.post("/{fid}/restore")
def restore_formation(fid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    source = db.query(Formation).filter(Formation.id == uuid.UUID(fid)).first()
    if source:
        db.query(Formation).filter(
            Formation.gid == source.gid, Formation.user_id == current_user.id
        ).update({"deleted_at": None})
        db.commit()
    return RedirectResponse(url="/admin/trash", status_code=303)


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
