"""
routers/profile.py — Dashboard + formulaire de profil complet
"""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import User, Profile, Language
from routers.auth import require_user

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    return templates.TemplateResponse("profile/dashboard.html", {
        "request": request,
        "current_user": current_user,
        "profile": profile,
    })


@router.get("/profile/edit", response_class=HTMLResponse)
def edit_profile_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    profile  = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    languages = db.query(Language).all()
    return templates.TemplateResponse("profile/edit.html", {
        "request": request,
        "current_user": current_user,
        "profile": profile,
        "languages": languages,
    })


@router.post("/profile/edit")
def edit_profile(
    request: Request,
    telephone: Optional[str]    = Form(None),
    linkedin_url: Optional[str] = Form(None),
    db: Session                 = Depends(get_db),
    current_user: User          = Depends(require_user),
):
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
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)
