"""
routers/formations.py — CRUD formations
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Formation, Language
from routers.auth import require_user

router = APIRouter(prefix="/formations", tags=["formations"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def list_formations(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    formations = db.query(Formation).filter(Formation.user_id == current_user.id).order_by(Formation.date_debut.desc()).all()
    languages  = db.query(Language).all()
    return templates.TemplateResponse("formations/list.html", {
        "request": request,
        "current_user": current_user,
        "formations": formations,
        "languages": languages,
    })


@router.get("/new", response_class=HTMLResponse)
def new_formation_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("formations/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "formation": None,
    })


@router.post("/new")
def create_formation(
    request: Request,
    diplome: str              = Form(...),
    etablissement: str        = Form(...),
    date_debut: date          = Form(...),
    date_fin: Optional[date]  = Form(None),
    description: Optional[str] = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    f = Formation(
        id=uuid.uuid4(),
        gid=uuid.uuid4(),
        user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        diplome=diplome,
        etablissement=etablissement,
        date_debut=date_debut,
        date_fin=date_fin,
        description=description or None,
    )
    db.add(f)
    db.commit()
    return RedirectResponse(url="/formations/", status_code=303)


@router.get("/{fid}/edit", response_class=HTMLResponse)
def edit_formation_page(fid: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    f = db.query(Formation).filter(Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id).first()
    if not f:
        return RedirectResponse(url="/formations/", status_code=303)
    languages = db.query(Language).all()
    return templates.TemplateResponse("formations/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "formation": f,
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
    f = db.query(Formation).filter(Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id).first()
    if f:
        f.diplome       = diplome
        f.etablissement = etablissement
        f.date_debut    = date_debut
        f.date_fin      = date_fin
        f.description   = description or None
        f.language_id   = uuid.UUID(language_id)
        db.commit()
    return RedirectResponse(url="/formations/", status_code=303)


@router.post("/{fid}/delete")
def delete_formation(fid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    f = db.query(Formation).filter(Formation.id == uuid.UUID(fid), Formation.user_id == current_user.id).first()
    if f:
        db.delete(f)
        db.commit()
    return RedirectResponse(url="/formations/", status_code=303)
