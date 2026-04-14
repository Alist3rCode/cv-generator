"""
routers/users.py — Gestion des utilisateurs (inscription, admin)
"""

import uuid

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Organisation, UserOrganisation, RoleEnum
from routers.auth import hash_password, require_user, is_admin

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="templates")


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    orgs = db.query(Organisation).all()
    return templates.TemplateResponse("users/register.html", {"request": request, "organisations": orgs})


@router.post("/register")
def register(
    request: Request,
    email: str         = Form(...),
    password: str      = Form(...),
    nom: str           = Form(...),
    prenom: str        = Form(...),
    organisation_id: str = Form(...),
    db: Session        = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        orgs = db.query(Organisation).all()
        return templates.TemplateResponse(
            "users/register.html",
            {"request": request, "error": "Cet email est déjà utilisé.", "organisations": orgs},
            status_code=400,
        )
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(password),
        nom=nom,
        prenom=prenom,
    )
    db.add(user)
    db.flush()

    uo = UserOrganisation(
        id=uuid.uuid4(),
        user_id=user.id,
        organisation_id=uuid.UUID(organisation_id),
        role=RoleEnum.user,
    )
    db.add(uo)
    db.commit()
    return RedirectResponse(url="/login?registered=1", status_code=303)


@router.get("/", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Liste des utilisateurs — réservé aux admins."""
    users = db.query(User).all()
    return templates.TemplateResponse("users/list.html", {"request": request, "users": users, "current_user": current_user})
