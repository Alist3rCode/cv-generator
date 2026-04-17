"""
routers/exports.py — Génération et téléchargement des CV
"""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import (
    User, Language, Template, CVExport, ExportFormatEnum,
    Bio, Experience, Formation, Certification, Competence, Profile,
    UserOrganisation, ProfilLangue,
)
from routers.auth import require_user
from services.cv_generator import generate_cv_docx, convert_docx_to_pdf

router = APIRouter(prefix="/exports", tags=["exports"])
templates = Jinja2Templates(directory="templates")

EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_class=HTMLResponse)
def export_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).filter(Language.is_active == True).order_by(Language.sort_order, Language.nom).all()

    # Templates actifs des organisations de l'utilisateur
    org_ids = [uo.organisation_id for uo in current_user.user_organisations]
    active_templates = (
        db.query(Template)
        .filter(Template.organisation_id.in_(org_ids), Template.is_active == True)
        .all()
    ) if org_ids else []

    previous_exports = (
        db.query(CVExport)
        .filter(CVExport.user_id == current_user.id)
        .order_by(CVExport.generated_at.desc())
        .limit(10)
        .all()
    )

    uid = current_user.id

    # Totaux uniques (tous GIDs confondus)
    all_exp_gids  = {str(e.gid) for e in db.query(Experience).filter(Experience.user_id == uid, Experience.deleted_at == None).all()}
    all_form_gids = {str(f.gid) for f in db.query(Formation).filter(Formation.user_id == uid, Formation.deleted_at == None).all()}
    all_cert_gids = {str(c.gid) for c in db.query(Certification).filter(Certification.user_id == uid, Certification.deleted_at == None).all()}
    all_comp_gids = {str(c.gid) for c in db.query(Competence).filter(Competence.user_id == uid, Competence.deleted_at == None).all()}
    total_items = len(all_exp_gids) + len(all_form_gids) + len(all_cert_gids) + len(all_comp_gids) + 1  # +1 pour bio

    # Langues ayant au moins une donnée + % de complétion
    langs_with_data = set()
    langs_completion: dict = {}   # {lang_id_str: int 0-100}

    for lang in languages:
        lid     = lang.id
        lid_str = str(lid)

        k_exp  = len({str(e.gid) for e in db.query(Experience).filter(Experience.user_id == uid, Experience.language_id == lid, Experience.deleted_at == None).all()})
        k_form = len({str(f.gid) for f in db.query(Formation).filter(Formation.user_id == uid, Formation.language_id == lid, Formation.deleted_at == None).all()})
        k_cert = len({str(c.gid) for c in db.query(Certification).filter(Certification.user_id == uid, Certification.language_id == lid, Certification.deleted_at == None).all()})
        k_comp = len({str(c.gid) for c in db.query(Competence).filter(Competence.user_id == uid, Competence.language_id == lid, Competence.deleted_at == None).all()})
        has_bio = db.query(Bio).filter(Bio.user_id == uid, Bio.language_id == lid).first() is not None

        k_total = k_exp + k_form + k_cert + k_comp + (1 if has_bio else 0)
        if k_total > 0:
            langs_with_data.add(lid_str)
        pct = int(k_total / total_items * 100) if total_items > 0 else 0
        langs_completion[lid_str] = min(pct, 100)

    # Langue par défaut : français (code 'fr'), sinon première
    default_lang = next((l for l in languages if l.code == 'fr'), languages[0] if languages else None)

    return templates.TemplateResponse("exports/export.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "active_templates": active_templates,
        "previous_exports": previous_exports,
        "formats": ExportFormatEnum,
        "langs_with_data": langs_with_data,
        "langs_completion": langs_completion,
        "default_lang_id": str(default_lang.id) if default_lang else "",
    })


@router.post("/generate")
def generate_export(
    request: Request,
    template_id: str  = Form(...),
    language_id: str  = Form(...),
    format: str       = Form(...),
    nom: str          = Form(default=""),
    db: Session       = Depends(get_db),
    current_user: User = Depends(require_user),
):
    lang_uuid = uuid.UUID(language_id)
    tmpl_uuid = uuid.UUID(template_id)

    template = db.query(Template).filter(Template.id == tmpl_uuid).first()
    if not template:
        return RedirectResponse(url="/exports/?error=template_not_found", status_code=303)

    # Récupérer le profil complet dans la langue demandée
    profile_data = {
        "user":           current_user,
        "profile":        db.query(Profile).filter(Profile.user_id == current_user.id).first(),
        "bio":            db.query(Bio).filter(Bio.user_id == current_user.id, Bio.language_id == lang_uuid).first(),
        "experiences":    db.query(Experience).filter(Experience.user_id == current_user.id, Experience.language_id == lang_uuid, Experience.deleted_at == None).order_by(Experience.date_debut.desc()).all(),
        "formations":     db.query(Formation).filter(Formation.user_id == current_user.id, Formation.language_id == lang_uuid, Formation.deleted_at == None).order_by(Formation.date_debut.desc()).all(),
        "certifications": db.query(Certification).filter(Certification.user_id == current_user.id, Certification.language_id == lang_uuid, Certification.deleted_at == None).order_by(Certification.date_obtention.desc()).all(),
        "competences":     db.query(Competence).filter(Competence.user_id == current_user.id, Competence.language_id == lang_uuid).all(),
        "profil_langues":  db.query(ProfilLangue).filter(ProfilLangue.user_id == current_user.id).order_by(ProfilLangue.created_at).all(),
    }

    export_id  = uuid.uuid4()
    export_fmt = ExportFormatEnum(format)

    docx_path = EXPORT_DIR / f"{export_id}.docx"
    try:
        generate_cv_docx(template.fichier_path, profile_data, str(docx_path))
    except Exception:
        import traceback
        tb = traceback.format_exc()
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse({"error": tb}, status_code=500)
        return JSONResponse({"error": tb}, status_code=500)

    if export_fmt == ExportFormatEnum.pdf:
        pdf_path = EXPORT_DIR / f"{export_id}.pdf"
        try:
            convert_docx_to_pdf(str(docx_path), str(pdf_path))
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        final_path = str(pdf_path)
    else:
        final_path = str(docx_path)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    # Nom par défaut : <nom template> <JJ/MM/AAAA HH:MM>
    export_nom = nom.strip() or f"{template.nom} - {now.strftime('%d/%m/%Y %H:%M')}"
    export = CVExport(
        id=export_id,
        user_id=current_user.id,
        template_id=tmpl_uuid,
        language_id=lang_uuid,
        format=export_fmt,
        nom=export_nom,
        fichier_path=final_path,
        generated_at=now,
    )
    db.add(export)
    db.commit()

    # Si appelé via fetch (JS), retourner JSON pour mise à jour sans rechargement
    if request.headers.get("X-Requested-With") == "fetch":
        lang_obj = db.query(Language).filter(Language.id == lang_uuid).first()
        return JSONResponse({
            "export_id":    str(export_id),
            "nom":          export_nom,
            "format":       export_fmt.value,
            "generated_at": now.strftime("%d/%m/%Y %H:%M"),
            "download_url": f"/exports/{export_id}/download",
            "lang_code":    lang_obj.code if lang_obj else "",
            "lang_nom":     lang_obj.nom if lang_obj else "",
        })

    return RedirectResponse(url=f"/exports/{export_id}/download", status_code=303)


@router.get("/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    export = db.query(CVExport).filter(CVExport.id == uuid.UUID(export_id), CVExport.user_id == current_user.id).first()
    if not export or not export.fichier_path or not Path(export.fichier_path).exists():
        return RedirectResponse(url="/exports/?error=file_not_found", status_code=303)

    filename = f"CV_{current_user.nom}_{current_user.prenom}.{export.format.value}"
    return FileResponse(export.fichier_path, filename=filename)


@router.post("/delete-all")
def delete_all_exports(db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    exports = db.query(CVExport).filter(CVExport.user_id == current_user.id).all()
    for export in exports:
        if export.fichier_path:
            Path(export.fichier_path).unlink(missing_ok=True)
        db.delete(export)
    db.commit()
    return RedirectResponse(url="/exports/", status_code=303)


@router.post("/{export_id}/delete")
def delete_export(export_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    export = db.query(CVExport).filter(
        CVExport.id == uuid.UUID(export_id),
        CVExport.user_id == current_user.id,
    ).first()
    if export:
        if export.fichier_path:
            Path(export.fichier_path).unlink(missing_ok=True)
        db.delete(export)
        db.commit()
    return RedirectResponse(url="/exports/", status_code=303)
