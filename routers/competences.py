"""
routers/competences.py — CRUD compétences (hard & soft skills)
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Competence, Language, SkillTypeEnum, SkillLevelEnum
from routers.auth import require_user

router = APIRouter(prefix="/competences", tags=["competences"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def list_competences(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    competences = db.query(Competence).filter(Competence.user_id == current_user.id).order_by(Competence.type, Competence.nom).all()
    languages   = db.query(Language).all()
    return templates.TemplateResponse("competences/list.html", {
        "request": request,
        "current_user": current_user,
        "competences": competences,
        "languages": languages,
        "skill_types": SkillTypeEnum,
        "skill_levels": SkillLevelEnum,
    })


@router.get("/new", response_class=HTMLResponse)
def new_competence_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("competences/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "comp": None,
        "skill_types": SkillTypeEnum,
        "skill_levels": SkillLevelEnum,
    })


@router.post("/new")
def create_competence(
    nom: str         = Form(...),
    type: str        = Form(...),
    niveau: int      = Form(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    c = Competence(
        id=uuid.uuid4(),
        gid=uuid.uuid4(),
        user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        nom=nom,
        type=SkillTypeEnum(type),
        niveau=SkillLevelEnum(niveau),
    )
    db.add(c)
    db.commit()
    return RedirectResponse(url="/competences/", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_competence_page(cid: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    c = db.query(Competence).filter(Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id).first()
    if not c:
        return RedirectResponse(url="/competences/", status_code=303)
    languages = db.query(Language).all()
    return templates.TemplateResponse("competences/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "comp": c,
        "skill_types": SkillTypeEnum,
        "skill_levels": SkillLevelEnum,
    })


@router.post("/{cid}/edit")
def update_competence(
    cid: str,
    nom: str         = Form(...),
    type: str        = Form(...),
    niveau: int      = Form(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    c = db.query(Competence).filter(Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id).first()
    if c:
        c.nom         = nom
        c.type        = SkillTypeEnum(type)
        c.niveau      = SkillLevelEnum(niveau)
        c.language_id = uuid.UUID(language_id)
        db.commit()
    return RedirectResponse(url="/competences/", status_code=303)


@router.post("/{cid}/delete")
def delete_competence(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    c = db.query(Competence).filter(Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse(url="/competences/", status_code=303)
