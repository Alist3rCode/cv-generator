"""
routers/certifications.py — CRUD certifications
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Certification, Language
from routers.auth import require_user

router = APIRouter(prefix="/certifications", tags=["certifications"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def list_certifications(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    certs     = db.query(Certification).filter(Certification.user_id == current_user.id).order_by(Certification.date_obtention.desc()).all()
    languages = db.query(Language).all()
    return templates.TemplateResponse("certifications/list.html", {
        "request": request,
        "current_user": current_user,
        "certifications": certs,
        "languages": languages,
    })


@router.get("/new", response_class=HTMLResponse)
def new_certification_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    return templates.TemplateResponse("certifications/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "cert": None,
    })


@router.post("/new")
def create_certification(
    titre: str                = Form(...),
    organisme: str            = Form(...),
    date_obtention: date      = Form(...),
    date_fin: Optional[date]  = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    c = Certification(
        id=uuid.uuid4(),
        gid=uuid.uuid4(),
        user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        titre=titre,
        organisme=organisme,
        date_obtention=date_obtention,
        date_fin=date_fin,
    )
    db.add(c)
    db.commit()
    return RedirectResponse(url="/certifications/", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_certification_page(cid: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    c = db.query(Certification).filter(Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id).first()
    if not c:
        return RedirectResponse(url="/certifications/", status_code=303)
    languages = db.query(Language).all()
    return templates.TemplateResponse("certifications/form.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "cert": c,
    })


@router.post("/{cid}/edit")
def update_certification(
    cid: str,
    titre: str                = Form(...),
    organisme: str            = Form(...),
    date_obtention: date      = Form(...),
    date_fin: Optional[date]  = Form(None),
    language_id: str          = Form(...),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    c = db.query(Certification).filter(Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id).first()
    if c:
        c.titre          = titre
        c.organisme      = organisme
        c.date_obtention = date_obtention
        c.date_fin       = date_fin
        c.language_id    = uuid.UUID(language_id)
        db.commit()
    return RedirectResponse(url="/certifications/", status_code=303)


@router.post("/{cid}/delete")
def delete_certification(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    c = db.query(Certification).filter(Certification.id == uuid.UUID(cid), Certification.user_id == current_user.id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse(url="/certifications/", status_code=303)
