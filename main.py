"""
main.py — Point d'entrée FastAPI
CV Generator App
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db
from routers import auth, users, profile, experiences, formations, certifications, competences, templates, exports

app = FastAPI(title="CV Generator", version="1.0.0")

# Fichiers statiques (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates Jinja2
templates_jinja = Jinja2Templates(directory="templates")

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


@app.on_event("startup")
def on_startup():
    """Initialise la base de données au démarrage."""
    init_db()


@app.get("/")
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")
