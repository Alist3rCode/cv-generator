"""
routers/profile.py — Dashboard + formulaire de profil complet (avec bio multi-langue)
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Language, Bio, Experience, Formation, Competence, Certification, ProfilLangue, CEFRLevelEnum, CEFR_LABELS
from routers.auth import require_user

router = APIRouter(tags=["profile"])
templates = Jinja2Templates(directory="templates")


def compute_completion(user_id, db: Session) -> tuple[int, dict]:
    """Calcule le % de complétion du profil (5 critères = 20% chacun)."""
    criteria = {
        "bio":        db.query(Bio).filter(Bio.user_id == user_id).count() > 0,
        "experience": db.query(Experience).filter(Experience.user_id == user_id).count() > 0,
        "formation":  db.query(Formation).filter(Formation.user_id == user_id).count() > 0,
        "competence": db.query(Competence).filter(Competence.user_id == user_id).count() > 0,
        "langue":     db.query(ProfilLangue).filter(ProfilLangue.user_id == user_id).count() > 0,
    }
    completed = sum(1 for v in criteria.values() if v)
    return int(completed / len(criteria) * 100), criteria


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    completion, criteria = compute_completion(current_user.id, db)

    # Donnees pour le resume CV
    languages     = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()
    default_lang  = languages[0] if languages else None

    bio = None
    if default_lang:
        bio = db.query(Bio).filter(
            Bio.user_id == current_user.id,
            Bio.language_id == default_lang.id,
        ).first()

    all_exps   = db.query(Experience).filter(Experience.user_id == current_user.id, Experience.deleted_at == None).order_by(Experience.date_debut.asc()).all()
    all_forms  = db.query(Formation).filter(Formation.user_id == current_user.id, Formation.deleted_at == None).order_by(Formation.date_debut.desc()).all()
    all_certs  = db.query(Certification).filter(Certification.user_id == current_user.id, Certification.deleted_at == None).order_by(Certification.date_obtention.desc()).all()
    all_comps  = db.query(Competence).filter(Competence.user_id == current_user.id).all()

    def _dedup(items):
        seen, result = set(), []
        for item in items:
            if item.gid not in seen:
                seen.add(item.gid)
                result.append(item)
        return result

    from models import SkillTypeEnum
    comps_dedup   = _dedup(all_comps)
    hard_count    = sum(1 for c in comps_dedup if c.type == SkillTypeEnum.hard)
    soft_count    = sum(1 for c in comps_dedup if c.type == SkillTypeEnum.soft)

    exps_dedup = _dedup(all_exps)  # triées ASC pour la timeline

    # Sérialiser pour la timeline JS (vis-timeline)
    def _exp_to_dict(exp):
        return {
            "id":          str(exp.id),
            "titre_poste": exp.titre_poste,
            "entreprise":  exp.entreprise or "",
            "date_debut":  exp.date_debut.strftime("%Y-%m-%d"),
            "date_fin":    exp.date_fin.strftime("%Y-%m-%d") if exp.date_fin else None,
        }
    exps_asc_json = [_exp_to_dict(e) for e in exps_dedup]

    # ── Nuage de mots : poids = niveau * nb_occurrences_dans_expériences ──
    # Compter les occurrences de chaque GID dans toutes les expériences
    from collections import Counter as _Counter
    gid_counts: _Counter = _Counter()
    for exp in exps_dedup:
        for gid in (exp.hard_skills or []):
            gid_counts[gid] += 1
        for gid in (exp.soft_skills or []):
            gid_counts[gid] += 1

    # Construire la liste {nom, weight} pour le nuage
    cloud_words = []
    seen_gids: set = set()
    for comp in comps_dedup:
        if comp.gid in seen_gids:
            continue
        seen_gids.add(comp.gid)
        gid_str = str(comp.gid)
        count   = gid_counts.get(gid_str, 0)
        # Compétences sans expérience associée : poids minimal = niveau seul
        weight  = comp.niveau.value * max(count, 1)
        cloud_words.append({"nom": comp.nom, "weight": weight, "type": comp.type.value})

    # Normaliser : ramener weight entre 1 et 10 pour l'affichage
    if cloud_words:
        max_w = max(w["weight"] for w in cloud_words)
        for w in cloud_words:
            w["size"] = round(1 + (w["weight"] / max_w) * 9, 2)

    langue_count = db.query(ProfilLangue).filter(ProfilLangue.user_id == current_user.id).count()

    from datetime import date as _date
    return templates.TemplateResponse("profile/dashboard.html", {
        "request":        request,
        "current_user":   current_user,
        "completion":     completion,
        "criteria":       criteria,
        "bio":            bio,
        "experiences":    list(reversed(exps_dedup)),   # DESC pour la liste résumé
        "experiences_asc": exps_asc_json,               # ASC pour la timeline (dicts JSON)
        "formations":     _dedup(all_forms),
        "certifications": _dedup(all_certs),
        "hard_count":     hard_count,
        "soft_count":     soft_count,
        "now_year":       _date.today().year,
        "cloud_words":    cloud_words,
        "langue_count":   langue_count,
    })


@router.get("/profile/edit", response_class=HTMLResponse)
def edit_profile_page(
    request: Request,
    language_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    profile   = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    languages = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()

    # Langue active
    active_language = languages[0] if languages else None
    if language_id:
        found = db.query(Language).filter(Language.id == uuid.UUID(language_id)).first()
        if found:
            active_language = found

    # Bio pour la langue active
    bio = None
    if active_language:
        bio = db.query(Bio).filter(
            Bio.user_id == current_user.id,
            Bio.language_id == active_language.id,
        ).first()

    # Quelles langues ont déjà une bio sauvegardée (dict pour la macro lang_tabs)
    bios_by_lang = {
        str(b.language_id): b
        for b in db.query(Bio).filter(Bio.user_id == current_user.id).all()
    }

    profil_langues = db.query(ProfilLangue).filter(
        ProfilLangue.user_id == current_user.id
    ).order_by(ProfilLangue.created_at).all()

    # Poste traduit : bio.poste pour la langue active, sinon profile.poste comme fallback
    profile_poste = (bio.poste if bio and bio.poste else (profile.poste or '')) if bio else (profile.poste or '')

    return templates.TemplateResponse("profile/edit.html", {
        "request":         request,
        "current_user":    current_user,
        "profile":         profile,
        "languages":       languages,
        "active_language": active_language,
        "bio":             bio,
        "bios_by_lang":    bios_by_lang,
        "profil_langues":  profil_langues,
        "cefr_levels":     [(e.value, CEFR_LABELS[e.value]) for e in CEFRLevelEnum],
        "profile_poste":   profile_poste,
    })


@router.post("/profile/edit")
def edit_profile(
    request: Request,
    telephone: Optional[str]    = Form(None),
    linkedin_url: Optional[str] = Form(None),
    poste: Optional[str]        = Form(None),
    bio_texte: Optional[str]    = Form(None),
    language_id: Optional[str]  = Form(None),
    # Langues parlées : listes parallèles
    langue_ids:     list[str]   = Form(default=[]),
    langue_noms:    list[str]   = Form(default=[]),
    langue_niveaux: list[str]   = Form(default=[]),
    db: Session                 = Depends(get_db),
    current_user: User          = Depends(require_user),
):
    # Sauvegarder le profil (téléphone, LinkedIn) — poste est désormais dans Bio par langue
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if profile:
        profile.telephone    = telephone or None
        profile.linkedin_url = linkedin_url or None
        # Conserver profile.poste comme fallback si aucune bio traduite ne le fournit
        if poste and not profile.poste:
            profile.poste = poste or None
    else:
        profile = Profile(
            id=uuid.uuid4(),
            user_id=current_user.id,
            telephone=telephone or None,
            linkedin_url=linkedin_url or None,
            poste=poste or None,
        )
        db.add(profile)

    # ── Langues parlées ──────────────────────────────────────────────────────
    # Supprimer toutes les langues existantes et recréer (formulaire liste complète)
    db.query(ProfilLangue).filter(ProfilLangue.user_id == current_user.id).delete()
    for nom, niveau_str in zip(langue_noms, langue_niveaux):
        nom = nom.strip()
        if not nom or not niveau_str:
            continue
        try:
            niveau_enum = CEFRLevelEnum(niveau_str)
        except ValueError:
            continue
        db.add(ProfilLangue(
            id=uuid.uuid4(),
            user_id=current_user.id,
            nom=nom,
            niveau=niveau_enum,
        ))
    # ────────────────────────────────────────────────────────────────────────

    # Sauvegarder la bio (texte + poste traduit) pour la langue active
    lang_id_str = (language_id or "").strip()
    if lang_id_str:
        try:
            lang_uuid = uuid.UUID(lang_id_str)
        except ValueError:
            lang_uuid = None
        if lang_uuid:
            bio = db.query(Bio).filter(
                Bio.user_id == current_user.id,
                Bio.language_id == lang_uuid,
            ).first()
            has_content = (bio_texte and bio_texte.strip()) or (poste and poste.strip())
            if bio:
                if has_content:
                    if bio_texte is not None:
                        bio.texte = bio_texte if bio_texte.strip() else bio.texte
                    bio.poste = poste or None
                else:
                    db.delete(bio)
            elif has_content:
                bio = Bio(
                    id=uuid.uuid4(),
                    user_id=current_user.id,
                    language_id=lang_uuid,
                    texte=bio_texte or "",
                    poste=poste or None,
                )
                db.add(bio)

    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True})
    redirect_lang = f"?language_id={language_id}" if language_id else ""
    return RedirectResponse(url=f"/profile/edit{redirect_lang}", status_code=303)
