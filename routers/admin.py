"""
routers/admin.py — Pages d'administration (corbeille, gestion utilisateurs)
"""

import uuid
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import User, Experience, Formation, Certification, UserOrganisation, RoleEnum
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


def _is_site_admin(user: User, db: Session) -> bool:
    """Un utilisateur est 'admin' s'il est admin d'au moins une organisation."""
    return db.query(UserOrganisation).filter(
        UserOrganisation.user_id == user.id,
        UserOrganisation.role == RoleEnum.admin,
    ).first() is not None


PAGE_SIZE = 20


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    q: str = Query(default="", alias="q"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if not _is_site_admin(current_user, db):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard", status_code=303)

    query = db.query(User)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(User.nom.ilike(term), User.prenom.ilike(term), User.email.ilike(term))
        )

    total  = query.count()
    users  = query.order_by(User.nom, User.prenom).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    pages  = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    # Pour chaque user, récupérer s'il est admin d'au moins une org
    user_org_map = {}
    for uo in db.query(UserOrganisation).filter(
        UserOrganisation.user_id.in_([u.id for u in users])
    ).all():
        user_org_map.setdefault(str(uo.user_id), []).append(uo)

    return templates.TemplateResponse("admin/users.html", {
        "request":      request,
        "current_user": current_user,
        "users":        users,
        "user_org_map": user_org_map,
        "q":            q,
        "page":         page,
        "pages":        pages,
        "total":        total,
    })


@router.post("/admin/users/{user_id}/toggle-admin")
def toggle_admin(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if not _is_site_admin(current_user, db):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    uid = uuid.UUID(user_id)
    # On agit sur toutes les UserOrganisation de cet utilisateur
    uo_list = db.query(UserOrganisation).filter(UserOrganisation.user_id == uid).all()

    if not uo_list:
        return JSONResponse({"error": "Aucune organisation pour cet utilisateur"}, status_code=404)

    # Si au moins un rôle est admin → retirer tous les droits admin
    # Sinon → passer tous en admin
    is_currently_admin = any(uo.role == RoleEnum.admin for uo in uo_list)
    new_role = RoleEnum.user if is_currently_admin else RoleEnum.admin

    for uo in uo_list:
        uo.role = new_role
    db.commit()

    return JSONResponse({"is_admin": new_role == RoleEnum.admin})


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
