"""
main.py — Point d'entrée FastAPI
CV Generator App
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("cv_generator")

from database import init_db, SessionLocal
from routers import auth, users, profile, experiences, formations, certifications, competences, templates, exports, admin

app = FastAPI(title="CV Generator", version="1.0.0")

# Templates Jinja2 — déclaré tôt pour les exception handlers
templates_jinja = Jinja2Templates(directory="templates")

from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

_ERROR_MESSAGES = {
    400: ("Requête invalide",        "La requête envoyée est incorrecte ou mal formée."),
    401: ("Non authentifié",         "Vous devez être connecté pour accéder à cette page."),
    403: ("Accès refusé",            "Vous n'avez pas les droits nécessaires pour accéder à cette ressource."),
    404: ("Page introuvable",        "La page que vous cherchez n'existe pas ou a été déplacée."),
    500: ("Erreur serveur",          "Une erreur interne s'est produite. Réessayez dans quelques instants."),
}

async def _render_error(request: Request, status_code: int, detail: str = ""):
    title, msg = _ERROR_MESSAGES.get(status_code, ("Erreur", detail))
    return templates_jinja.TemplateResponse("error.html", {
        "request":     request,
        "status_code": status_code,
        "title":       title,
        "detail":      msg,
    }, status_code=status_code)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code in (301, 302, 303, 307, 308):
        from fastapi.responses import RedirectResponse
        location = (exc.headers or {}).get("Location", "/")
        return RedirectResponse(url=location, status_code=exc.status_code)
    return await _render_error(request, exc.status_code, str(exc.detail))

@app.exception_handler(HTTPException)
async def fastapi_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (301, 302, 303, 307, 308):
        from fastapi.responses import RedirectResponse
        location = (exc.headers or {}).get("Location", "/")
        return RedirectResponse(url=location, status_code=exc.status_code)
    return await _render_error(request, exc.status_code, str(exc.detail))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("Unhandled exception on %s\n%s", request.url, tb)
    return templates_jinja.TemplateResponse("error.html", {
        "request":     request,
        "status_code": 500,
        "title":       "Erreur serveur",
        "detail":      "Une erreur interne s'est produite. Réessayez dans quelques instants.",
    }, status_code=500)


class AdminContextMiddleware(BaseHTTPMiddleware):
    """
    Injecte request.state.is_admin pour chaque requête authentifiée.
    Utilisé dans base.html pour afficher/masquer le menu Templates.
    """
    async def dispatch(self, request: Request, call_next):
        request.state.is_admin = False
        token = request.cookies.get("access_token")
        if token:
            try:
                import uuid as _uuid
                from jose import jwt as _jwt
                from routers.auth import SECRET_KEY, ALGORITHM
                from models import User, UserOrganisation, RoleEnum
                payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("sub")
                if user_id:
                    db = SessionLocal()
                    try:
                        uo = db.query(UserOrganisation).filter(
                            UserOrganisation.user_id == _uuid.UUID(user_id),
                            UserOrganisation.role == RoleEnum.admin,
                        ).first()
                        request.state.is_admin = uo is not None
                    finally:
                        db.close()
            except Exception:
                pass
        return await call_next(request)


app.add_middleware(AdminContextMiddleware)

# Fichiers statiques (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

def _exp_duration_filter(exp):
    """Filtre Jinja2 : calcule la durée d'une expérience en texte lisible."""
    from datetime import date
    start = exp.date_debut
    end   = exp.date_fin or date.today()
    total_months = (end.year - start.year) * 12 + (end.month - start.month)
    if total_months < 1:
        total_months = 1
    years  = total_months // 12
    months = total_months % 12
    parts  = []
    if years:
        parts.append(f"{years} an{'s' if years > 1 else ''}")
    if months:
        parts.append(f"{months} mois")
    return " ".join(parts) if parts else "< 1 mois"


# Enregistrer le filtre sur TOUS les routeurs qui utilisent Jinja2
def _register_filters():
    import routers.experiences as _exp_router
    import routers.profile as _profile_router
    for mod in [_exp_router, _profile_router]:
        mod.templates.env.filters["exp_duration"] = _exp_duration_filter


_register_filters()

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profile.router)
app.include_router(experiences.router)
app.include_router(formations.router)
app.include_router(certifications.router)
app.include_router(competences.router)
app.include_router(templates.router)
app.include_router(exports.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    """Initialise la base de données au démarrage et s'assure que les langues par défaut existent."""
    init_db()
    _seed_default_languages()
    _seed_default_admin()


def _seed_default_languages():
    """Insère les 5 langues par défaut si elles n'existent pas encore."""
    import uuid as _uuid
    from database import SessionLocal
    from models import Language

    default_langs = [
        ("fr", "Français"),
        ("gb", "English"),
        ("es", "Español"),
        ("it", "Italiano"),
        ("de", "Deutsch"),
    ]
    db = SessionLocal()
    try:
        # Migration : renommer le code "en" -> "gb" d'abord (avant l'insert "gb")
        lang_en = db.query(Language).filter(Language.code == "en").first()
        if lang_en:
            lang_en.code = "gb"
            db.flush()
        # Puis insérer les langues manquantes
        for code, nom in default_langs:
            if not db.query(Language).filter(Language.code == code).first():
                db.add(Language(id=_uuid.uuid4(), code=code, nom=nom))
        db.commit()
    finally:
        db.close()


def _seed_default_admin():
    """Crée l'organisation et le compte admin par défaut s'ils n'existent pas encore."""
    import os as _os
    import uuid as _uuid
    from database import SessionLocal
    from models import Organisation, User, UserOrganisation, RoleEnum
    from routers.auth import hash_password

    admin_email    = _os.getenv("ADMIN_EMAIL",    "admin@example.com")
    admin_password = _os.getenv("ADMIN_PASSWORD", "admin1234")

    db = SessionLocal()
    try:
        org = db.query(Organisation).filter(Organisation.nom == "Ma Société").first()
        if not org:
            org = Organisation(id=_uuid.uuid4(), nom="Ma Société")
            db.add(org)
            db.flush()

        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                id=_uuid.uuid4(),
                email=admin_email,
                password_hash=hash_password(admin_password),
                nom="Admin",
                prenom="Super",
            )
            db.add(admin)
            db.flush()
            db.add(UserOrganisation(
                id=_uuid.uuid4(),
                user_id=admin.id,
                organisation_id=org.id,
                role=RoleEnum.admin,
            ))
        db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")
