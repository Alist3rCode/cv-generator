"""
routers/templates.py — Import et gestion des templates Word (admin)
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Template, Organisation, UserOrganisation, RoleEnum
from routers.auth import require_user

router = APIRouter(prefix="/templates", tags=["templates"])
templates_jinja = Jinja2Templates(directory="templates")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads/templates"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _get_user_orgs_as_admin(user: User, db: Session):
    """Retourne les organisations où l'utilisateur est admin."""
    return (
        db.query(Organisation)
        .join(UserOrganisation, UserOrganisation.organisation_id == Organisation.id)
        .filter(UserOrganisation.user_id == user.id, UserOrganisation.role == RoleEnum.admin)
        .all()
    )


def _require_admin(user: User, db: Session):
    orgs = _get_user_orgs_as_admin(user, db)
    if not orgs:
        return RedirectResponse(url="/dashboard", status_code=303)
    return None


@router.get("/", response_class=HTMLResponse)
def list_templates(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    admin_orgs = _get_user_orgs_as_admin(current_user, db)
    admin_org_ids = [o.id for o in admin_orgs]
    tmplts = (
        db.query(Template)
        .filter(Template.organisation_id.in_(admin_org_ids))
        .order_by(Template.is_active.desc())
        .all()
    ) if admin_org_ids else []
    from models import Experience, Formation, Certification, Competence
    def _tc():
        uid = current_user.id
        return sum([
            db.query(Experience).filter(Experience.user_id == uid, Experience.deleted_at != None).count(),
            db.query(Formation).filter(Formation.user_id == uid, Formation.deleted_at != None).count(),
            db.query(Certification).filter(Certification.user_id == uid, Certification.deleted_at != None).count(),
            db.query(Competence).filter(Competence.user_id == uid, Competence.deleted_at != None).count(),
        ])
    return templates_jinja.TemplateResponse("admin/templates_list.html", {
        "request": request,
        "current_user": current_user,
        "templates": tmplts,
        "admin_orgs": admin_orgs,
        "trash_count": _tc(),
    })


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    admin_orgs = _get_user_orgs_as_admin(current_user, db)
    from datetime import date
    return templates_jinja.TemplateResponse("admin/template_upload.html", {
        "request": request,
        "current_user": current_user,
        "admin_orgs": admin_orgs,
        "now": date.today(),
        "trash_count": 0,
    })


@router.post("/upload")
async def upload_template(
    request: Request,
    nom: str              = Form(...),
    organisation_id: str  = Form(...),
    fichier: UploadFile   = File(...),
    db: Session           = Depends(get_db),
    current_user: User    = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    # Vérification que le fichier est bien un .docx
    if not fichier.filename.endswith(".docx"):
        admin_orgs = _get_user_orgs_as_admin(current_user, db)
        return templates_jinja.TemplateResponse(
            "admin/template_upload.html",
            {"request": request, "current_user": current_user, "admin_orgs": admin_orgs, "error": "Seuls les fichiers .docx sont acceptés."},
            status_code=400,
        )

    org_id = uuid.UUID(organisation_id)

    # Sauvegarder le fichier
    file_id   = uuid.uuid4()
    save_path = UPLOAD_DIR / f"{file_id}.docx"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(fichier.file, f)

    template = Template(
        id=file_id,
        nom=nom,
        fichier_path=str(save_path),
        organisation_id=org_id,
        uploaded_by=current_user.id,
        is_active=True,
    )
    db.add(template)
    db.commit()
    return RedirectResponse(url="/templates/", status_code=303)


@router.post("/{tid}/toggle")
def toggle_template(tid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    t = db.query(Template).filter(Template.id == uuid.UUID(tid)).first()
    if t:
        t.is_active = not t.is_active
        db.commit()
    return RedirectResponse(url="/templates/", status_code=303)


@router.post("/{tid}/delete")
def delete_template(tid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    from models import CVExport
    t = db.query(Template).filter(Template.id == uuid.UUID(tid)).first()
    if t:
        # Détacher les exports liés sans les supprimer (historique conservé)
        db.query(CVExport).filter(CVExport.template_id == t.id).update({"template_id": None})
        db.flush()
        Path(t.fichier_path).unlink(missing_ok=True)
        db.delete(t)
        db.commit()
    return RedirectResponse(url="/templates/", status_code=303)
