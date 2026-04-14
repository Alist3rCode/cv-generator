"""
routers/auth.py — Authentification (login / logout)
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserOrganisation

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="templates")

SECRET_KEY = "changeme-secret-key-in-production"
ALGORITHM  = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 heures

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Lit le token JWT depuis le cookie de session."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except Exception:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Dépendance — redirige vers /login si non connecté."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user


def is_admin(user: User, organisation_id, db: Session) -> bool:
    """Vérifie si l'utilisateur est admin de l'organisation."""
    from models import RoleEnum
    uo = db.query(UserOrganisation).filter(
        UserOrganisation.user_id == user.id,
        UserOrganisation.organisation_id == organisation_id,
        UserOrganisation.role == RoleEnum.admin,
    ).first()
    return uo is not None


# ── Pages ──────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
def login(
    request: Request,
    email: str    = Form(...),
    password: str = Form(...),
    db: Session   = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Email ou mot de passe incorrect."},
            status_code=401,
        )
    token = create_access_token({"sub": str(user.id)})
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response
