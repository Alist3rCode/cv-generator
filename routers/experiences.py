"""
routers/experiences.py — CRUD expériences professionnelles
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Experience, Language
from routers.auth import require_user

router = APIRouter(prefix="/experiences", tags=["experiences"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def list_experiences(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    experiences = db.query(Experience).filter(Experience.user_id == current_user.id).order_by(Experience.date_debut.desc()).all()
    languages   = db.query(Language).all()
    return templates.TemplateResponse("experiences/list.html", {
        "request": request,
        "current_user": current_user,
        "experiences": experiences,
        "languages": languages,
    })


@router.get("/new", response_class=HTMLResponse)
def new_experience_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("experiences/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "exp": None,
    })


@router.post("/new")
def create_experience(
    request: Request,
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
        id=uuid.uuid4(),
        gid=uuid.uuid4(),
        user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        titre_poste=titre_poste,
        entreprise=entreprise,
        location=location or None,
        date_debut=date_debut,
        date_fin=date_fin,
        project_summary=project_summary or None,
        description=description or None,
    )
    db.add(exp)
    db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.get("/{exp_id}/edit", response_class=HTMLResponse)
def edit_experience_page(exp_id: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    exp = db.query(Experience).filter(Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id).first()
    if not exp:
        return RedirectResponse(url="/experiences/", status_code=303)
    languages = db.query(Language).all()
    return templates.TemplateResponse("experiences/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "exp": exp,
    })


@router.post("/{exp_id}/edit")
def update_experience(
    exp_id: str,
    request: Request,
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
    exp = db.query(Experience).filter(Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id).first()
    if exp:
        exp.titre_poste     = titre_poste
        exp.entreprise      = entreprise
        exp.location        = location or None
        exp.date_debut      = date_debut
        exp.date_fin        = date_fin
        exp.project_summary = project_summary or None
        exp.description     = description or None
        exp.language_id     = uuid.UUID(language_id)
        db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.post("/{exp_id}/delete")
def delete_experience(exp_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    exp = db.query(Experience).filter(Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id).first()
    if exp:
        db.delete(exp)
        db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)
