"""
routers/exports.py — Génération et téléchargement des CV
"""

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

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/", response_class=HTMLResponse)
def export_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    languages = db.query(Language).all()

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

    return templates.TemplateResponse("exports/export.html", {
        "request": request,
        "current_user": current_user,
        "languages": languages,
        "active_templates": active_templates,
        "previous_exports": previous_exports,
        "formats": ExportFormatEnum,
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
        convert_docx_to_pdf(str(docx_path), str(pdf_path))
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
        return JSONResponse({
            "export_id":    str(export_id),
            "nom":          export_nom,
            "format":       export_fmt.value,
            "generated_at": now.strftime("%d/%m/%Y %H:%M"),
            "download_url": f"/exports/{export_id}/download",
        })

    return RedirectResponse(url=f"/exports/{export_id}/download", status_code=303)


@router.get("/{export_id}/download")
def download_export(export_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_user)):
    export = db.query(CVExport).filter(CVExport.id == uuid.UUID(export_id), CVExport.user_id == current_user.id).first()
    if not export or not export.fichier_path or not Path(export.fichier_path).exists():
        return RedirectResponse(url="/exports/?error=file_not_found", status_code=303)

    filename = f"CV_{current_user.nom}_{current_user.prenom}.{export.format.value}"
    return FileResponse(export.fichier_path, filename=filename)


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
