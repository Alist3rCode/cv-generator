"""
routers/experiences.py — CRUD expériences professionnelles (multi-langue via GID)
"""

import json
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Experience, Language, Competence, SkillTypeEnum, SkillLevelEnum
from routers.auth import require_user

router = APIRouter(prefix="/experiences", tags=["experiences"])

def _parse_date(value):
    """Convertit une chaine en date (YYYY-MM ou YYYY-MM-DD), 1er du mois, None si vide."""
    from datetime import date as _date
    if not value or not value.strip():
        return None
    v = value.strip()
    if len(v) == 7:          # format "YYYY-MM" depuis type="month"
        return _date(int(v[:4]), int(v[5:7]), 1)
    return _date.fromisoformat(v)

templates = Jinja2Templates(directory="templates")


def _dedup_by_gid(items):
    """Retourne un item par GID (le premier rencontré)."""
    seen, result = set(), []
    for item in items:
        if item.gid not in seen:
            seen.add(item.gid)
            result.append(item)
    return result


def _parse_skills_json(value: str):
    """Parse une chaine JSON en liste de GID strings. Retourne [] si invalide."""
    if not value or not value.strip():
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(g) for g in parsed]
        return []
    except Exception:
        return []


def _load_comps_for_user(db: Session, user_id, prefer_lang_code="fr"):
    """
    Charge toutes les compétences de l'utilisateur, dédupliquées par GID.
    Préfère le français (ou la première langue disponible).
    Retourne (comps_hard, comps_soft) — listes de dicts {gid, nom, niveau}.
    """
    all_comps = db.query(Competence).filter(Competence.user_id == user_id).all()

    # Grouper par GID
    by_gid: dict = {}
    for c in all_comps:
        gid = str(c.gid)
        by_gid.setdefault(gid, []).append(c)

    # Choisir le meilleur représentant par GID
    from models import Language as Lang
    fr_langs = db.query(Lang).filter(Lang.code == prefer_lang_code).all()
    fr_lang_ids = {str(l.id) for l in fr_langs}

    comps_hard, comps_soft = [], []
    for gid, rows in by_gid.items():
        chosen = None
        # Préférer français
        for r in rows:
            if str(r.language_id) in fr_lang_ids:
                chosen = r
                break
        if chosen is None:
            chosen = rows[0]
        entry = {"gid": gid, "nom": chosen.nom, "niveau": chosen.niveau.value, "type": chosen.type.value}
        if chosen.type == SkillTypeEnum.hard:
            comps_hard.append(entry)
        else:
            comps_soft.append(entry)

    comps_hard.sort(key=lambda x: x["nom"].lower())
    comps_soft.sort(key=lambda x: x["nom"].lower())
    return comps_hard, comps_soft


@router.get("/", response_class=HTMLResponse)
def list_experiences(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    all_exps  = db.query(Experience).filter(Experience.user_id == current_user.id, Experience.deleted_at == None).order_by(Experience.date_debut.desc()).all()
    experiences = _dedup_by_gid(all_exps)
    if not experiences:
        return RedirectResponse(url="/experiences/new", status_code=302)
    languages   = db.query(Language).all()
    # Langues disponibles par GID
    langs_by_gid = {}
    for exp in all_exps:
        gid = str(exp.gid)
        langs_by_gid.setdefault(gid, set()).add(str(exp.language_id))
    return templates.TemplateResponse("experiences/list.html", {
        "request": request, "current_user": current_user,
        "experiences": experiences, "languages": languages,
        "langs_by_gid": langs_by_gid,
    })


@router.get("/new", response_class=HTMLResponse)
def new_experience_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()
    comps_hard, comps_soft = _load_comps_for_user(db, current_user.id)
    return templates.TemplateResponse("experiences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "exp": None, "gid": None,
        "active_language_id": str(languages[0].id) if languages else None,
        "translations_by_lang": {}, "source_id": None,
        "comps_hard": comps_hard, "comps_soft": comps_soft,
        "exp_hard_gids": [], "exp_soft_gids": [],
    })


@router.post("/new")
def create_experience(
    titre_poste: str          = Form(...),
    entreprise: str           = Form(...),
    location: Optional[str]   = Form(None),
    date_debut: str           = Form(...),
    date_fin: Optional[str]   = Form(None),
    project_summary: Optional[str] = Form(None),
    description: Optional[str]    = Form(None),
    language_id: str          = Form(...),
    hard_skills_json: str     = Form(""),
    soft_skills_json: str     = Form(""),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    hard_skills = _parse_skills_json(hard_skills_json)
    soft_skills = _parse_skills_json(soft_skills_json)
    exp = Experience(
        id=uuid.uuid4(), gid=uuid.uuid4(), user_id=current_user.id,
        language_id=uuid.UUID(language_id),
        titre_poste=titre_poste, entreprise=entreprise,
        location=location or None, date_debut=_parse_date(date_debut), date_fin=_parse_date(date_fin),
        project_summary=project_summary or None, description=description or None,
        hard_skills=hard_skills or None,
        soft_skills=soft_skills or None,
    )
    db.add(exp)
    db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.get("/{exp_id}/edit", response_class=HTMLResponse)
def edit_experience_page(
    exp_id: str, request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/experiences/", status_code=303)

    languages = db.query(Language).all()

    # Toutes les traductions du même GID
    translations = db.query(Experience).filter(
        Experience.gid == source.gid, Experience.user_id == current_user.id
    ).all()
    translations_by_lang = {str(t.language_id): t for t in translations}

    # Langue active
    active_lang_id = language_id or str(source.language_id)
    exp = translations_by_lang.get(active_lang_id, None)

    # Compétences disponibles
    comps_hard, comps_soft = _load_comps_for_user(db, current_user.id)

    # GIDs assignés à cette expérience (depuis source — language-independent)
    exp_hard_gids = [str(g) for g in (source.hard_skills or [])]
    exp_soft_gids = [str(g) for g in (source.soft_skills or [])]

    return templates.TemplateResponse("experiences/form.html", {
        "request": request, "current_user": current_user,
        "languages": languages, "exp": exp, "source": source,
        "gid": str(source.gid), "source_id": exp_id,
        "active_language_id": active_lang_id,
        "translations_by_lang": translations_by_lang,
        "comps_hard": comps_hard, "comps_soft": comps_soft,
        "exp_hard_gids": exp_hard_gids, "exp_soft_gids": exp_soft_gids,
    })


@router.post("/{exp_id}/edit")
def update_experience(
    exp_id: str,
    titre_poste: str          = Form(...),
    entreprise: str           = Form(...),
    location: Optional[str]   = Form(None),
    date_debut: str           = Form(...),
    date_fin: Optional[str]   = Form(None),
    project_summary: Optional[str] = Form(None),
    description: Optional[str]    = Form(None),
    language_id: str          = Form(...),
    hard_skills_json: str     = Form(""),
    soft_skills_json: str     = Form(""),
    db: Session               = Depends(get_db),
    current_user: User        = Depends(require_user),
):
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if not source:
        return RedirectResponse(url="/experiences/", status_code=303)

    hard_skills = _parse_skills_json(hard_skills_json)
    soft_skills = _parse_skills_json(soft_skills_json)

    lang_uuid = uuid.UUID(language_id)
    existing = db.query(Experience).filter(
        Experience.gid == source.gid, Experience.user_id == current_user.id,
        Experience.language_id == lang_uuid,
    ).first()

    if existing:
        existing.titre_poste = titre_poste; existing.entreprise = entreprise
        existing.location = location or None; existing.date_debut = _parse_date(date_debut)
        existing.date_fin = _parse_date(date_fin); existing.project_summary = project_summary or None
        existing.description = description or None
    else:
        db.add(Experience(
            id=uuid.uuid4(), gid=source.gid, user_id=current_user.id,
            language_id=lang_uuid, titre_poste=titre_poste, entreprise=entreprise,
            location=location or None, date_debut=_parse_date(date_debut), date_fin=_parse_date(date_fin),
            project_summary=project_summary or None, description=description or None,
        ))

    # Mettre à jour les skills sur TOUTES les traductions du même GID
    all_translations = db.query(Experience).filter(
        Experience.gid == source.gid, Experience.user_id == current_user.id
    ).all()
    for t in all_translations:
        t.hard_skills = hard_skills or None
        t.soft_skills = soft_skills or None

    db.commit()
    return RedirectResponse(url=f"/experiences/{exp_id}/edit?language_id={language_id}", status_code=303)


@router.post("/{exp_id}/soft-delete")
def soft_delete_experience(exp_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Désactive l'expérience (soft delete) sans la supprimer de la BDD."""
    from datetime import datetime as _dt
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if source:
        # Marquer toutes les traductions du même GID
        db.query(Experience).filter(
            Experience.gid == source.gid, Experience.user_id == current_user.id
        ).update({"deleted_at": _dt.utcnow()})
        db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.post("/{exp_id}/restore")
def restore_experience(exp_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    """Réactive une expérience désactivée."""
    source = db.query(Experience).filter(Experience.id == uuid.UUID(exp_id)).first()
    if source:
        db.query(Experience).filter(
            Experience.gid == source.gid, Experience.user_id == current_user.id
        ).update({"deleted_at": None})
        db.commit()
    return RedirectResponse(url="/admin/trash", status_code=303)


@router.post("/{exp_id}/delete")
def delete_experience(exp_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    # Supprime toutes les traductions du même GID
    source = db.query(Experience).filter(
        Experience.id == uuid.UUID(exp_id), Experience.user_id == current_user.id
    ).first()
    if source:
        db.query(Experience).filter(
            Experience.gid == source.gid, Experience.user_id == current_user.id
        ).delete()
        db.commit()
    return RedirectResponse(url="/experiences/", status_code=303)


@router.post("/competences/inline")
def create_competence_inline(
    nom: str         = Form(...),
    type: str        = Form(...),
    niveau: int      = Form(...),
    language_id: str = Form(...),
    db: Session      = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Crée une compétence à la volée depuis le picker et retourne le JSON de la nouvelle compétence."""
    new_gid = uuid.uuid4()
    comp = Competence(
        id=uuid.uuid4(), gid=new_gid, user_id=current_user.id,
        language_id=uuid.UUID(language_id), nom=nom,
        type=SkillTypeEnum(type), niveau=SkillLevelEnum(niveau),
    )
    db.add(comp)
    db.commit()
    return JSONResponse({
        "gid": str(new_gid),
        "nom": nom,
        "niveau": niveau,
        "type": type,
    })
