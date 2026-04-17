"""
routers/competences.py — CRUD compétences (multi-langue via GID)
"""

import uuid
import datetime as _dt
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Competence, Experience, Language, SkillTypeEnum, SkillLevelEnum
from routers.auth import require_user

router = APIRouter(prefix="/competences", tags=["competences"])
templates = Jinja2Templates(directory="templates")


def _dedup_by_gid(items):
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


@router.get("/", response_class=HTMLResponse)
def list_competences(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_items   = db.query(Competence).filter(Competence.user_id == current_user.id, Competence.deleted_at == None).order_by(Competence.type, Competence.nom).all()
    competences = _dedup_by_gid(all_items)
    if not competences:
        return RedirectResponse(url="/competences/new", status_code=302)
    languages   = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()
    langs_by_gid: dict = {}
    for c in all_items:
        langs_by_gid.setdefault(str(c.gid), set()).add(str(c.language_id))

    total_gids = len(langs_by_gid)
    # Nombre de GIDs traduits par langue (pour barre de progression)
    per_lang_counts = {}
    for lang in languages:
        lid = str(lang.id)
        per_lang_counts[lid] = sum(1 for langs in langs_by_gid.values() if lid in langs)

    # Convertir sets → listes pour usage JS (tojson)
    langs_by_gid_js = {gid: list(langs) for gid, langs in langs_by_gid.items()}

    return templates.TemplateResponse("competences/list.html", {
        "request": request, "current_user": current_user,
        "competences": competences, "languages": languages,
        "langs_by_gid": langs_by_gid,
        "langs_by_gid_js": langs_by_gid_js,
        "per_lang_counts": per_lang_counts,
        "total_gids": total_gids,
        "skill_types": SkillTypeEnum, "skill_levels": SkillLevelEnum,
    })


@router.get("/new", response_class=HTMLResponse)
def new_competence_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()
    return templates.TemplateResponse("competences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "comp": None, "gid": None,
        "active_language_id": str(languages[0].id) if languages else None,
        "translations_by_lang": {}, "source_id": None,
        "skill_types": SkillTypeEnum, "skill_levels": SkillLevelEnum,
    })


@router.post("/new")
def create_competence(
    nom: str         = Form(...),
    type: str        = Form(...),
    niveau: int      = Form(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    db.add(Competence(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id), nom=nom,
        type=SkillTypeEnum(type), niveau=SkillLevelEnum(niveau),
    ))
    db.commit()
    return RedirectResponse(url="/competences/", status_code=303)


@router.get("/{cid}/edit", response_class=HTMLResponse)
def edit_competence_page(
    cid: str, request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/competences/", status_code=303)

    languages = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()
    translations = db.query(Competence).filter(
        Competence.gid == source.gid, Competence.user_id == current_user.id
    ).all()
    translations_by_lang = {str(t.language_id): t for t in translations}
    active_lang_id = language_id or str(source.language_id)
    comp = translations_by_lang.get(active_lang_id, None)

    return templates.TemplateResponse("competences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "comp": comp, "source": source,
        "gid": str(source.gid), "source_id": cid,
        "active_language_id": active_lang_id,
        "translations_by_lang": translations_by_lang,
        "skill_types": SkillTypeEnum, "skill_levels": SkillLevelEnum,
    })


@router.post("/{cid}/edit")
def update_competence(
    cid: str,
    request: Request,
    nom: str         = Form(...),
    type: str        = Form(...),
    niveau: int      = Form(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/competences/", status_code=303)

    lang_uuid = uuid.UUID(language_id)
    existing = db.query(Competence).filter(
        Competence.gid == source.gid, Competence.user_id == current_user.id,
        Competence.language_id == lang_uuid,
    ).first()

    if existing:
        existing.nom = nom; existing.type = SkillTypeEnum(type); existing.niveau = SkillLevelEnum(niveau)
    else:
        db.add(Competence(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, nom=nom,
            type=SkillTypeEnum(type), niveau=SkillLevelEnum(niveau),
        ))
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": True})
    return RedirectResponse(url=f"/competences/{cid}/edit?language_id={language_id}", status_code=303)


@router.get("/{cid}/usage")
def get_competence_usage(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Retourne les expériences (dédupliquées par GID) qui utilisent cette compétence."""
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if not source:
        return JSONResponse({"experiences": []})

    gid_str = str(source.gid)
    all_exps = db.query(Experience).filter(Experience.user_id == current_user.id).all()

    seen_exp_gids = set()
    result = []
    for exp in all_exps:
        exp_gid = str(exp.gid)
        if exp_gid in seen_exp_gids:
            continue
        hard = [str(g) for g in (exp.hard_skills or [])]
        soft = [str(g) for g in (exp.soft_skills or [])]
        if gid_str in hard or gid_str in soft:
            seen_exp_gids.add(exp_gid)
            result.append({
                "id": str(exp.id),
                "titre_poste": exp.titre_poste,
                "entreprise": exp.entreprise,
            })

    return JSONResponse({"experiences": result})


@router.post("/{cid}/soft-delete")
def soft_delete_competence(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Soft-delete : marque toutes les traductions du GID comme supprimées."""
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if source:
        db.query(Competence).filter(
            Competence.gid == source.gid, Competence.user_id == current_user.id
        ).update({"deleted_at": _dt.datetime.utcnow()})
        db.commit()
    return RedirectResponse(url="/competences/", status_code=303)


@router.post("/{cid}/restore")
def restore_competence(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Restaure une compétence depuis la corbeille."""
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if source:
        db.query(Competence).filter(
            Competence.gid == source.gid, Competence.user_id == current_user.id
        ).update({"deleted_at": None})
        db.commit()
    return RedirectResponse(url="/admin/trash", status_code=303)


@router.post("/{cid}/delete")
def delete_competence(cid: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Suppression définitive (depuis la corbeille)."""
    source = db.query(Competence).filter(
        Competence.id == uuid.UUID(cid), Competence.user_id == current_user.id
    ).first()
    if source:
        gid_str = str(source.gid)
        # Retirer le GID de toutes les expériences qui le référencent
        all_exps = db.query(Experience).filter(Experience.user_id == current_user.id).all()
        for exp in all_exps:
            hard = [str(g) for g in (exp.hard_skills or [])]
            soft = [str(g) for g in (exp.soft_skills or [])]
            if gid_str in hard:
                exp.hard_skills = [g for g in hard if g != gid_str] or None
            if gid_str in soft:
                exp.soft_skills = [g for g in soft if g != gid_str] or None
        db.query(Competence).filter(
            Competence.gid == source.gid, Competence.user_id == current_user.id
        ).delete()
        db.commit()
    return RedirectResponse(url="/admin/trash", status_code=303)
