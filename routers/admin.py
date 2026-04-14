"""
routers/admin.py — Pages d'administration (corbeille, etc.)
"""

import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Experience, Formation, Certification
from routers.auth import require_user

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="templates")


def _dedup(items):
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


@router.get("/admin/trash", response_class=HTMLResponse)
def admin_trash(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    experiences = _dedup(db.query(Experience).filter(
        Experience.user_id == current_user.id, Experience.deleted_at != None
    ).order_by(Experience.deleted_at.desc()).all())

    formations = _dedup(db.query(Formation).filter(
        Formation.user_id == current_user.id, Formation.deleted_at != None
    ).order_by(Formation.deleted_at.desc()).all())

    certifications = _dedup(db.query(Certification).filter(
        Certification.user_id == current_user.id, Certification.deleted_at != None
    ).order_by(Certification.deleted_at.desc()).all())

    return templates.TemplateResponse("admin/trash.html", {
        "request": request,
        "current_user": current_user,
        "experiences": experiences,
        "formations": formations,
        "certifications": certifications,
    })
