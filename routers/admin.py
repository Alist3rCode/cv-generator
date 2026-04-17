"""
routers/admin.py — Pages d'administration (corbeille, utilisateurs, organisations)
"""

import uuid
from typing import List
from fastapi import APIRouter, Body, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import (
    User, Experience, Formation, Certification, Competence,
    Organisation, UserOrganisation, RoleEnum, Language,
)
from routers.auth import require_user

router = APIRouter(tags=["admin"])
templates = Jinja2Templates(directory="templates")


# ── helpers ────────────────────────────────────────────────────────────────

def _dedup(items):
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


def _is_site_admin(user: User, db: Session) -> bool:
    return db.query(UserOrganisation).filter(
        UserOrganisation.user_id == user.id,
        UserOrganisation.role == RoleEnum.admin,
    ).first() is not None


def _require_admin(current_user: User, db: Session):
    """Retourne RedirectResponse si non admin, None sinon."""
    if not _is_site_admin(current_user, db):
        return RedirectResponse(url="/dashboard", status_code=303)
    return None


def _trash_count(user_id, db: Session) -> int:
    counts = [
        db.query(Experience).filter(Experience.user_id == user_id, Experience.deleted_at != None).count(),
        db.query(Formation).filter(Formation.user_id == user_id, Formation.deleted_at != None).count(),
        db.query(Certification).filter(Certification.user_id == user_id, Certification.deleted_at != None).count(),
        db.query(Competence).filter(Competence.user_id == user_id, Competence.deleted_at != None).count(),
    ]
    return sum(counts)


PAGE_SIZE = 20


# ── index ──────────────────────────────────────────────────────────────────

@router.get("/admin/", response_class=HTMLResponse)
@router.get("/admin", response_class=HTMLResponse)
def admin_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard
    return RedirectResponse(url="/admin/organisations", status_code=303)


# ── utilisateurs ───────────────────────────────────────────────────────────

@router.get("/admin/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    q: str = Query(default="", alias="q"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    query = db.query(User)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(User.nom.ilike(term), User.prenom.ilike(term), User.email.ilike(term))
        )

    total = query.count()
    users = query.order_by(User.nom, User.prenom).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

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
        "trash_count":  _trash_count(current_user.id, db),
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
    uo_list = db.query(UserOrganisation).filter(UserOrganisation.user_id == uid).all()

    if not uo_list:
        return JSONResponse({"error": "Aucune organisation pour cet utilisateur"}, status_code=404)

    is_currently_admin = any(uo.role == RoleEnum.admin for uo in uo_list)
    new_role = RoleEnum.user if is_currently_admin else RoleEnum.admin

    for uo in uo_list:
        uo.role = new_role
    db.commit()

    return JSONResponse({"is_admin": new_role == RoleEnum.admin})


# ── corbeille ──────────────────────────────────────────────────────────────

@router.get("/admin/trash", response_class=HTMLResponse)
def admin_trash(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    # Récupère tous les items supprimés de tous les utilisateurs, groupés par user
    all_users = db.query(User).order_by(User.nom, User.prenom).all()
    user_map = {str(u.id): u for u in all_users}

    def _items_by_user(query_result):
        grouped = {}
        for item in query_result:
            uid = str(item.user_id)
            grouped.setdefault(uid, []).append(item)
        return grouped

    exp_by_user  = _items_by_user(_dedup(db.query(Experience).filter(
        Experience.deleted_at != None).order_by(Experience.deleted_at.desc()).all()))
    form_by_user = _items_by_user(_dedup(db.query(Formation).filter(
        Formation.deleted_at != None).order_by(Formation.deleted_at.desc()).all()))
    cert_by_user = _items_by_user(_dedup(db.query(Certification).filter(
        Certification.deleted_at != None).order_by(Certification.deleted_at.desc()).all()))
    comp_by_user = _items_by_user(_dedup(db.query(Competence).filter(
        Competence.deleted_at != None).order_by(Competence.deleted_at.desc()).all()))

    # Liste des user_id qui ont au moins un item en corbeille
    user_ids_with_trash = set(exp_by_user) | set(form_by_user) | set(cert_by_user) | set(comp_by_user)
    users_with_trash = [u for u in all_users if str(u.id) in user_ids_with_trash]

    tc = sum(len(v) for v in exp_by_user.values()) + \
         sum(len(v) for v in form_by_user.values()) + \
         sum(len(v) for v in cert_by_user.values()) + \
         sum(len(v) for v in comp_by_user.values())

    return templates.TemplateResponse("admin/trash.html", {
        "request":           request,
        "current_user":      current_user,
        "users_with_trash":  users_with_trash,
        "exp_by_user":       exp_by_user,
        "form_by_user":      form_by_user,
        "cert_by_user":      cert_by_user,
        "comp_by_user":      comp_by_user,
        "trash_count":       tc,
    })


# ── organisations ──────────────────────────────────────────────────────────

@router.get("/admin/organisations", response_class=HTMLResponse)
def admin_organisations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    orgs = db.query(Organisation).order_by(Organisation.nom).all()
    # Count members per org
    member_counts = {}
    for uo in db.query(UserOrganisation).all():
        oid = str(uo.organisation_id)
        member_counts[oid] = member_counts.get(oid, 0) + 1

    return templates.TemplateResponse("admin/organisations.html", {
        "request":       request,
        "current_user":  current_user,
        "orgs":          orgs,
        "member_counts": member_counts,
        "trash_count":   _trash_count(current_user.id, db),
    })


@router.get("/admin/organisations/new", response_class=HTMLResponse)
def admin_org_new(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    return templates.TemplateResponse("admin/organisation_form.html", {
        "request":      request,
        "current_user": current_user,
        "org":          None,
        "trash_count":  _trash_count(current_user.id, db),
    })


@router.post("/admin/organisations/new")
def admin_org_create(
    request: Request,
    nom: str = Form(...),
    adresse: str = Form(default=""),
    email: str = Form(default=""),
    telephone: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    org = Organisation(
        nom=nom.strip(),
        adresse=adresse.strip() or None,
        email=email.strip() or None,
        telephone=telephone.strip() or None,
    )
    db.add(org)
    db.commit()
    return RedirectResponse(url="/admin/organisations", status_code=303)


@router.get("/admin/organisations/{org_id}/edit", response_class=HTMLResponse)
def admin_org_edit(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    org = db.query(Organisation).filter(Organisation.id == uuid.UUID(org_id)).first()
    if not org:
        return RedirectResponse(url="/admin/organisations", status_code=303)

    # Members with their roles
    members = (
        db.query(UserOrganisation, User)
        .join(User, User.id == UserOrganisation.user_id)
        .filter(UserOrganisation.organisation_id == org.id)
        .order_by(User.nom, User.prenom)
        .all()
    )
    # All users not yet in this org
    member_ids = [uo.user_id for uo, _ in members]
    other_users = db.query(User).filter(User.id.notin_(member_ids)).order_by(User.nom, User.prenom).all()

    return templates.TemplateResponse("admin/organisation_form.html", {
        "request":      request,
        "current_user": current_user,
        "org":          org,
        "members":      members,
        "other_users":  other_users,
        "trash_count":  _trash_count(current_user.id, db),
    })


@router.post("/admin/organisations/{org_id}/edit")
def admin_org_update(
    org_id: str,
    nom: str = Form(...),
    adresse: str = Form(default=""),
    email: str = Form(default=""),
    telephone: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    org = db.query(Organisation).filter(Organisation.id == uuid.UUID(org_id)).first()
    if org:
        org.nom = nom.strip()
        org.adresse = adresse.strip() or None
        org.email = email.strip() or None
        org.telephone = telephone.strip() or None
        db.commit()
    return RedirectResponse(url="/admin/organisations", status_code=303)


@router.post("/admin/organisations/{org_id}/delete")
def admin_org_delete(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    org = db.query(Organisation).filter(Organisation.id == uuid.UUID(org_id)).first()
    if org:
        db.query(UserOrganisation).filter(UserOrganisation.organisation_id == org.id).delete()
        db.delete(org)
        db.commit()
    return RedirectResponse(url="/admin/organisations", status_code=303)


# ── membres d'une organisation ─────────────────────────────────────────────

@router.post("/admin/organisations/{org_id}/add-member")
def admin_org_add_member(
    org_id: str,
    user_id: str = Form(...),
    role: str = Form(default="user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    oid = uuid.UUID(org_id)
    uid = uuid.UUID(user_id)
    existing = db.query(UserOrganisation).filter(
        UserOrganisation.organisation_id == oid,
        UserOrganisation.user_id == uid,
    ).first()
    if not existing:
        uo = UserOrganisation(
            organisation_id=oid,
            user_id=uid,
            role=RoleEnum.admin if role == "admin" else RoleEnum.user,
        )
        db.add(uo)
        db.commit()
    return RedirectResponse(url=f"/admin/organisations/{org_id}/edit", status_code=303)


@router.post("/admin/organisations/{org_id}/remove-member/{uo_id}")
def admin_org_remove_member(
    org_id: str,
    uo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    uo = db.query(UserOrganisation).filter(UserOrganisation.id == uuid.UUID(uo_id)).first()
    if uo:
        db.delete(uo)
        db.commit()
    return RedirectResponse(url=f"/admin/organisations/{org_id}/edit", status_code=303)


# ── langues ────────────────────────────────────────────────────────────────

@router.get("/admin/languages", response_class=HTMLResponse)
def admin_languages(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    languages = db.query(Language).order_by(Language.sort_order, Language.nom).all()
    return templates.TemplateResponse("admin/languages.html", {
        "request":      request,
        "current_user": current_user,
        "languages":    languages,
        "trash_count":  _trash_count(current_user.id, db),
    })


@router.post("/admin/languages/{lang_id}/toggle")
def admin_language_toggle(
    lang_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if not _is_site_admin(current_user, db):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    lang = db.query(Language).filter(Language.id == uuid.UUID(lang_id)).first()
    if not lang:
        return JSONResponse({"error": "Not found"}, status_code=404)

    # Le français ne peut pas être désactivé
    if lang.code == "fr":
        return JSONResponse({"error": "Le français ne peut pas être désactivé"}, status_code=400)

    lang.is_active = not lang.is_active
    db.commit()
    return JSONResponse({"is_active": lang.is_active})


@router.post("/admin/languages/new")
def admin_language_create(
    request: Request,
    nom: str  = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    code = code.strip().lower()
    nom  = nom.strip()

    # Vérifier doublon
    existing = db.query(Language).filter(Language.code == code).first()
    if existing:
        return JSONResponse({"error": f"Le code « {code} » existe déjà."}, status_code=400)

    # Affecter le sort_order suivant
    max_order = db.query(Language).count()
    lang = Language(id=uuid.uuid4(), code=code, nom=nom, is_active=True, sort_order=max_order)
    db.add(lang)
    db.commit()

    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({
            "id":        str(lang.id),
            "code":      lang.code,
            "nom":       lang.nom,
            "is_active": True,
        })
    return RedirectResponse(url="/admin/languages", status_code=303)


@router.post("/admin/languages/reorder")
def admin_language_reorder(
    ids: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Reçoit une liste ordonnée d'IDs et met à jour sort_order."""
    if not _is_site_admin(current_user, db):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    for i, lid_str in enumerate(ids):
        try:
            lang = db.query(Language).filter(Language.id == uuid.UUID(lid_str)).first()
            if lang:
                lang.sort_order = i
        except Exception:
            pass
    db.commit()
    return JSONResponse({"ok": True})


@router.post("/admin/organisations/{org_id}/set-role/{uo_id}")
def admin_org_set_role(
    org_id: str,
    uo_id: str,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    guard = _require_admin(current_user, db)
    if guard:
        return guard

    uo = db.query(UserOrganisation).filter(UserOrganisation.id == uuid.UUID(uo_id)).first()
    if uo:
        uo.role = RoleEnum.admin if role == "admin" else RoleEnum.user
        db.commit()
    return RedirectResponse(url=f"/admin/organisations/{org_id}/edit", status_code=303)
