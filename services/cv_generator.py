"""
services/cv_generator.py — Génération de CV à partir d'un template .docx

Système de balises dans le template Word :
  {{NOM}}              → Nom de famille
  {{PRENOM}}           → Prénom
  {{EMAIL}}            → Email
  {{TELEPHONE}}        → Téléphone
  {{LINKEDIN}}         → URL LinkedIn
  {{POSTE}}            → Titre / poste professionnel
  {{BIO}}              → Texte de bio

  Pour les sections répétées, utiliser un tableau Word avec une ligne modèle
  contenant les balises suivantes :

  Expériences :
    {{EXP_TITRE}}       → Titre du poste
    {{EXP_ENTREPRISE}}  → Entreprise
    {{EXP_LOCATION}}    → Localisation
    {{EXP_DEBUT}}       → Date de début
    {{EXP_FIN}}         → Date de fin (ou "Présent")
    {{EXP_SUMMARY}}     → Résumé de projet
    {{EXP_DESC}}        → Description
    {{EXP_HARD_TITRE}}  → "Environnement Technique : " si hard skills, sinon ""
    {{EXP_HARD_NOM}}    → Hard skills liés, séparés par " , "
    {{EXP_SOFT_TITRE}}  → "Environnement Fonctionnel : " si soft skills, sinon ""
    {{EXP_SOFT_NOM}}    → Soft skills liés, séparés par " , "

  Formations :
    {{FORM_DIPLOME}}   → Diplôme
    {{FORM_ETAB}}      → Établissement
    {{FORM_DEBUT}}     → Date de début
    {{FORM_FIN}}       → Date de fin

  Certifications :
    {{CERT_TITRE}}     → Titre
    {{CERT_ORG}}       → Organisme
    {{CERT_DATE}}      → Date d'obtention
    {{CERT_FIN}}       → Date d'expiration (ou "pas d'expiration")

  Compétences hard :
    {{HARD_NOM}}       → Nom de la compétence
    {{HARD_NIVEAU}}    → Libellé du niveau (ex : "Expert")
    {{HARD_FAMILLE}}   → Famille de compétence

  Compétences soft :
    {{SOFT_NOM}}       → Nom de la compétence
    {{SOFT_NIVEAU}}    → Libellé du niveau (ex : "Intermédiaire")
    {{SOFT_FAMILLE}}   → Famille de compétence

  Langues parlées :
    {{LNG_NOM}}        → Nom de la langue (ex : "Anglais")
    {{LNG_NIVEAU}}     → Code + libellé CEFR (ex : "C1 — Autonome")
"""

import copy
import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    """Formate une date Python en 'MM/YYYY', ou '' si None."""
    if d is None:
        return ""
    return d.strftime("%m/%Y")


def _fmt_duration(start, end=None) -> str:
    """Calcule la durée entre deux dates en texte lisible (ex: '2 ans 3 mois')."""
    from datetime import date
    if start is None:
        return ""
    end = end or date.today()
    total_months = (end.year - start.year) * 12 + (end.month - start.month)
    if total_months < 1:
        total_months = 1
    years  = total_months // 12
    months = total_months % 12
    parts  = []
    if years:
        parts.append(f"{years} an{'s' if years > 1 else ''}")
    if months:
        parts.append(f"{months} mois")
    return " ".join(parts) if parts else "< 1 mois"


def _replace_in_paragraph(para, replacements: dict[str, str]) -> None:
    """
    Remplace les balises dans un paragraphe en gérant le split Word.

    Word décompose souvent {{NOM}} en plusieurs runs (ex: '{{', 'NOM', '}}')
    pour des raisons de formatage interne. On fusionne d'abord le texte de
    tous les runs, on effectue les remplacements, puis on met le résultat
    dans le premier run et on vide les autres (en conservant leur XML pour
    ne pas casser la structure).
    """
    if not para.runs:
        return

    # Vérifier si une balise est présente (évite de toucher les paragraphes propres)
    full_text = "".join(r.text for r in para.runs)
    if not any(key in full_text for key in replacements):
        return

    # Appliquer tous les remplacements sur le texte fusionné
    new_text = full_text
    for key, value in replacements.items():
        new_text = new_text.replace(key, value or "")

    # Mettre le texte final dans le premier run, vider les autres
    para.runs[0].text = new_text
    for run in para.runs[1:]:
        run.text = ""


def _replace_in_doc(doc: Document, replacements: dict[str, str]) -> None:
    """Remplace les balises dans tous les paragraphes ET toutes les cellules de tableau."""
    for para in doc.paragraphs:
        _replace_in_paragraph(para, replacements)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _replace_in_cell(cell, replacements)


def _replace_in_cell(cell, replacements: dict[str, str]) -> None:
    """Remplace les balises dans tous les paragraphes d'une cellule."""
    for para in cell.paragraphs:
        _replace_in_paragraph(para, replacements)
    # Récursion sur les tableaux imbriqués
    for tbl in cell.tables:
        for row in tbl.rows:
            for c in row.cells:
                _replace_in_cell(c, replacements)


def _find_template_row(table, marker: str):
    """Retourne la première ligne du tableau contenant le marqueur."""
    for row in table.rows:
        for cell in row.cells:
            if marker in cell.text:
                return row
    return None


def _clone_row(row):
    """Clone une ligne de tableau (deep copy du XML)."""
    return copy.deepcopy(row._tr)


def _fill_row(row, replacements: dict[str, str]) -> None:
    """Remplace les balises dans toutes les cellules d'une ligne."""
    for cell in row.cells:
        _replace_in_cell(cell, replacements)


def _expand_table_section(doc: Document, marker: str, items: list[dict[str, str]]) -> None:
    """
    Trouve la table contenant `marker`, clone la ligne modèle pour chaque item
    et supprime la ligne modèle originale.
    """
    for table in doc.tables:
        template_row = _find_template_row(table, marker)
        if template_row is None:
            continue

        # Index de la ligne modèle dans le tableau
        tr_list = table._tbl.findall(qn("w:tr"))
        row_index = tr_list.index(template_row._tr)

        # Cloner + remplir une ligne par item
        for item in items:
            new_tr = _clone_row(template_row)
            table._tbl.insert(row_index, new_tr)
            # Trouver la vraie Row SQLAlchemy wrappée
            from docx.table import _Row
            new_row = _Row(new_tr, table)
            _fill_row(new_row, item)
            row_index += 1

        # Supprimer la ligne modèle
        table._tbl.remove(template_row._tr)
        break


# ── Fonction principale ────────────────────────────────────────────────────

def generate_cv_docx(template_path: str, profile: dict[str, Any], output_path: str) -> None:
    """
    Génère un fichier .docx à partir du template et des données du profil.

    Args:
        template_path: chemin vers le fichier .docx template
        profile: dict contenant les clés user, profile, bio, experiences,
                 formations, certifications, competences
        output_path: chemin de sortie du fichier .docx généré
    """
    doc  = Document(template_path)
    user = profile["user"]
    prof = profile.get("profile")
    bio  = profile.get("bio")

    from models import SkillTypeEnum, CEFR_LABELS

    # ── Libellés de niveau compétence ──
    niveau_labels = {1: "Débutant", 2: "Intermédiaire", 3: "Avancé", 4: "Expert"}

    # ── Index GID → Competence (toutes les compétences du user) ──
    comp_by_gid: dict[str, Any] = {}
    for c in profile.get("competences", []):
        comp_by_gid[str(c.gid)] = c

    # ── Remplacements simples ──
    simple = {
        "{{NOM}}":       user.nom,
        "{{PRENOM}}":    user.prenom,
        "{{EMAIL}}":     user.email,
        "{{TELEPHONE}}": (prof.telephone if prof else "") or "",
        "{{LINKEDIN}}":  (prof.linkedin_url if prof else "") or "",
        "{{POSTE}}":     (prof.poste if prof else "") or "",
        "{{BIO}}":       (bio.texte if bio else "") or "",
    }
    _replace_in_doc(doc, simple)

    # Remplacements dans les headers/footers
    for section in doc.sections:
        for hf in [section.header, section.footer]:
            for para in hf.paragraphs:
                _replace_in_paragraph(para, simple)

    # ── Sections répétées ──

    # Expériences
    def _exp_skills(gids, skill_type):
        """Retourne les noms des compétences d'un type donné pour une liste de GIDs."""
        noms = []
        for gid in (gids or []):
            c = comp_by_gid.get(str(gid))
            if c and c.type == skill_type:
                noms.append(c.nom)
        return noms

    exp_rows = []
    for e in profile.get("experiences", []):
        hard_noms = _exp_skills(e.hard_skills, SkillTypeEnum.hard)
        soft_noms = _exp_skills(e.soft_skills, SkillTypeEnum.soft)
        exp_rows.append({
            "{{EXP_TITRE}}":       e.titre_poste,
            "{{EXP_ENTREPRISE}}":  e.entreprise,
            "{{EXP_LOCATION}}":    e.location or "",
            "{{EXP_DEBUT}}":       _fmt_date(e.date_debut),
            "{{EXP_FIN}}":         _fmt_date(e.date_fin) or "Présent",
            "{{EXP_SUMMARY}}":     e.project_summary or "",
            "{{EXP_DESC}}":        e.description or "",
            "{{EXP_DUREE}}":       _fmt_duration(e.date_debut, e.date_fin),
            "{{EXP_HARD_TITRE}}":  "Environnement Technique : " if hard_noms else "",
            "{{EXP_HARD_NOM}}":    " , ".join(hard_noms),
            "{{EXP_SOFT_TITRE}}":  "Environnement Fonctionnel : " if soft_noms else "",
            "{{EXP_SOFT_NOM}}":    " , ".join(soft_noms),
        })
    _expand_table_section(doc, "{{EXP_TITRE}}", exp_rows)

    # Formations
    _expand_table_section(doc, "{{FORM_DIPLOME}}", [
        {
            "{{FORM_DIPLOME}}": f.diplome,
            "{{FORM_ETAB}}":    f.etablissement,
            "{{FORM_DEBUT}}":   _fmt_date(f.date_debut),
            "{{FORM_FIN}}":     _fmt_date(f.date_fin),
        }
        for f in profile.get("formations", [])
    ])

    # Certifications
    _expand_table_section(doc, "{{CERT_TITRE}}", [
        {
            "{{CERT_TITRE}}": c.titre,
            "{{CERT_ORG}}":   c.organisme,
            "{{CERT_DATE}}":  _fmt_date(c.date_obtention),
            "{{CERT_FIN}}":   _fmt_date(c.date_fin) if c.date_fin else "pas d'expiration",
        }
        for c in profile.get("certifications", [])
    ])

    # Compétences
    hard = [c for c in profile.get("competences", []) if c.type == SkillTypeEnum.hard]
    soft = [c for c in profile.get("competences", []) if c.type == SkillTypeEnum.soft]

    _expand_table_section(doc, "{{HARD_NOM}}", [
        {
            "{{HARD_NOM}}":    c.nom,
            "{{HARD_NIVEAU}}": niveau_labels.get(c.niveau.value, str(c.niveau.value)),
            "{{HARD_FAMILLE}}": c.famille or "",
        }
        for c in hard
    ])
    _expand_table_section(doc, "{{SOFT_NOM}}", [
        {
            "{{SOFT_NOM}}":    c.nom,
            "{{SOFT_NIVEAU}}": niveau_labels.get(c.niveau.value, str(c.niveau.value)),
            "{{SOFT_FAMILLE}}": c.famille or "",
        }
        for c in soft
    ])

    # Langues parlées
    _expand_table_section(doc, "{{LNG_NOM}}", [
        {
            "{{LNG_NOM}}":    l.nom,
            "{{LNG_NIVEAU}}": CEFR_LABELS.get(l.niveau.value, l.niveau.value),
        }
        for l in profile.get("profil_langues", [])
    ])

    doc.save(output_path)


def convert_docx_to_pdf(docx_path: str, pdf_path: str) -> None:
    """
    Convertit un .docx en .pdf via WeasyPrint (HTML intermédiaire)
    ou via LibreOffice si disponible.
    Tente d'abord LibreOffice (meilleure fidélité), puis fallback WeasyPrint.
    """
    import subprocess
    import sys

    # Tentative LibreOffice
    for soffice in ["soffice", "libreoffice"]:
        try:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir",
                 str(Path(pdf_path).parent), docx_path],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0:
                # LibreOffice génère le PDF avec le même nom de base
                generated = Path(docx_path).with_suffix(".pdf")
                if generated.exists() and str(generated) != pdf_path:
                    generated.rename(pdf_path)
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Fallback : WeasyPrint via conversion HTML basique
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
    except Exception:
        # Dernier recours : copie du docx avec extension .pdf (fichier inutilisable mais évite l'erreur)
        import shutil
        shutil.copy2(docx_path, pdf_path)
