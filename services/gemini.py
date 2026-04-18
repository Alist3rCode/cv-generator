"""
services/gemini.py — Client Gemini pour l'import de CV et la traduction.

Les prompts sont définis ici (non configurables par les admins).
La clé API et le modèle sont lus depuis la DB (AIConfig) en priorité,
puis depuis les variables d'environnement en fallback.

Utilise le SDK officiel google-genai (pip install google-genai).
"""

import json
import os
import re


def _get_config() -> tuple[str, str]:
    """
    Retourne (api_key, model_name) depuis la DB ou l'env.
    Importe la DB ici pour éviter les imports circulaires.
    """
    try:
        from database import SessionLocal
        from models import AIConfig
        db = SessionLocal()
        try:
            cfg = db.query(AIConfig).filter(AIConfig.id == 1).first()
            if cfg and cfg.is_active and cfg.api_key:
                return cfg.api_key, cfg.model_name or "gemini-2.0-flash"
        finally:
            db.close()
    except Exception:
        pass

    api_key = os.getenv("GEMINI_API_KEY", "")
    model   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return api_key, model


def _parse_gemini_json(text: str) -> dict:
    """Parse la réponse Gemini : retire les blocs ```json ... ``` si présents."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


_IMPORT_PROMPT = """
Analyse ce CV et extrais toutes les informations disponibles.
La langue cible du formulaire est : {language_name}.
Si le CV est dans une autre langue, traduis les contenus vers {language_name}.

Retourne UNIQUEMENT un objet JSON valide (sans markdown, sans backticks) avec cette structure exacte :

{{
  "profile": {{
    "telephone": "numéro ou null",
    "linkedin_url": "URL ou null",
    "poste": "titre du poste actuel ou principal ou null"
  }},
  "bio": {{
    "texte": "texte de présentation ou profil professionnel, ou null"
  }},
  "profil_langues": [
    {{"nom": "Anglais", "niveau": "C1"}}
  ],
  "experiences": [
    {{
      "titre_poste": "intitulé du poste",
      "entreprise": "nom de l'entreprise",
      "location": "ville, pays ou null",
      "date_debut": "YYYY-MM-DD",
      "date_fin": "YYYY-MM-DD ou null si en cours",
      "project_summary": "résumé du projet ou contexte ou null",
      "description": "description détaillée des missions ou null"
    }}
  ],
  "formations": [
    {{
      "diplome": "intitulé du diplôme",
      "etablissement": "nom de l'établissement",
      "ville": "ville ou null",
      "date_debut": "YYYY-MM-DD",
      "date_fin": "YYYY-MM-DD ou null"
    }}
  ],
  "certifications": [
    {{
      "titre": "nom de la certification",
      "organisme": "organisme certificateur",
      "date_obtention": "YYYY-MM-DD",
      "date_fin": "YYYY-MM-DD ou null si pas d'expiration"
    }}
  ],
  "competences": {{
    "hard": [{{"nom": "Python", "famille": "Développement"}}],
    "soft": [{{"nom": "Communication", "famille": ""}}]
  }}
}}

Règles importantes :
- Niveaux CEFR pour profil_langues : A1, A2, B1, B2, C1, C2, NATIVE
- Dates : toujours au format YYYY-MM-DD strict.
  * Si seul le mois et l'année sont indiqués (ex: "06/2021"), utilise le 1er du mois : "2021-06-01".
  * Si seule l'année est indiquée (ex: "2019"), utilise le 1er janvier : "2019-01-01".
  * date_debut est OBLIGATOIRE pour chaque expérience et chaque formation. Si le CV ne mentionne aucune date de début, estime-la à partir du contexte (date_fin - durée approximative) ou utilise "2000-01-01" en dernier recours. Ne laisse jamais date_debut à null pour une expérience ou une formation.
  * date_fin = null uniquement si l'expérience ou le poste est en cours.
- Si une information n'est pas disponible : utilise null ou [] selon le type
- Retourne UNIQUEMENT du JSON valide, aucun texte avant ou après
"""

_TRANSLATE_PROMPT = """
Tu es un expert en traduction professionnelle de CV.
Traduis le contenu suivant de {source_language} vers {target_language}.

Voici les données à traduire au format JSON :
{payload_json}

Règles importantes :
- Conserve les champs "_gid" EXACTEMENT tels quels (ne les traduis pas, ce sont des identifiants UUID)
- Ne traduis PAS les noms propres d'entreprises et d'organismes (champs "entreprise" et "organisme")
- Traduis tous les autres champs textuels vers {target_language}
- Conserve la même structure JSON exacte
- Retourne UNIQUEMENT du JSON valide, sans markdown ni backticks
"""


class GeminiRateLimitError(RuntimeError):
    """Levée quand Gemini renvoie une erreur 429 (quota dépassé)."""
    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _handle_gemini_error(exc: Exception) -> None:
    """
    Transforme les exceptions google-genai en RuntimeError lisibles.
    Lève GeminiRateLimitError pour les 429, RuntimeError pour le reste.
    """
    exc_str = str(exc)
    exc_type = type(exc).__name__

    is_quota = (
        "429" in exc_str
        or "RESOURCE_EXHAUSTED" in exc_str.upper()
        or "ResourceExhausted" in exc_type
        or "quota exceeded" in exc_str.lower()
        or "rate limit" in exc_str.lower()
        or "too many requests" in exc_str.lower()
    )
    if is_quota:
        retry_after: int | None = None
        # Chercher "retryDelay" suivi de la valeur en secondes (ex: retryDelay: "8.833s")
        m = re.search(r"retryDelay[\":\s]+(\d+(?:\.\d+)?)\s*s", exc_str, re.IGNORECASE)
        if not m:
            m = re.search(r"retry[_\s]after[\":\s]+(\d+(?:\.\d+)?)", exc_str, re.IGNORECASE)
        if not m:
            m = re.search(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", exc_str, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d+(?:\.\d+)?)\s*second", exc_str, re.IGNORECASE)
        if m:
            try:
                retry_after = int(float(m.group(1))) + 1  # arrondi vers le haut
            except ValueError:
                pass
        msg = "Quota Gemini dépassé (trop de requêtes)."
        if retry_after:
            msg += f" Réessayez dans {retry_after} secondes."
        else:
            msg += " Réessayez dans quelques instants ou vérifiez votre quota sur console.cloud.google.com."
        raise GeminiRateLimitError(msg, retry_after_seconds=retry_after) from exc
    raise RuntimeError(f"Erreur Gemini : {exc_str}") from exc


def extract_cv_data(file_path: str, mime_type: str, language_name: str) -> dict:
    """
    Upload le fichier CV vers l'API Gemini File et extrait les données structurées.

    Raises:
        GeminiRateLimitError si le quota est dépassé (429)
        RuntimeError si la clé API est manquante ou si l'extraction échoue
    """
    from google import genai
    from google.genai import types

    api_key, model_name = _get_config()
    if not api_key:
        raise RuntimeError(
            "Aucune clé API Gemini configurée. "
            "Configurez-la dans Administration → Configuration IA ou dans la variable d'environnement GEMINI_API_KEY."
        )

    client = genai.Client(api_key=api_key)

    # Upload du fichier vers Gemini File API
    try:
        uploaded_file = client.files.upload(
            file=file_path,
            config=types.UploadFileConfig(mime_type=mime_type),
        )
    except Exception as e:
        _handle_gemini_error(e)

    try:
        prompt   = _IMPORT_PROMPT.format(language_name=language_name)
        response = client.models.generate_content(
            model=model_name,
            contents=[uploaded_file, prompt],
        )
        return _parse_gemini_json(response.text)
    except GeminiRateLimitError:
        raise
    except Exception as e:
        _handle_gemini_error(e)
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass


def translate_cv_data(payload: dict, source_lang_name: str, target_lang_name: str) -> dict:
    """
    Traduit les données CV d'une langue vers une autre via Gemini.

    Raises:
        GeminiRateLimitError si le quota est dépassé (429)
        RuntimeError si la clé API est manquante ou si la traduction échoue
    """
    from google import genai

    api_key, model_name = _get_config()
    if not api_key:
        raise RuntimeError(
            "Aucune clé API Gemini configurée. "
            "Configurez-la dans Administration → Configuration IA ou dans la variable d'environnement GEMINI_API_KEY."
        )

    client = genai.Client(api_key=api_key)

    prompt = _TRANSLATE_PROMPT.format(
        source_language=source_lang_name,
        target_language=target_lang_name,
        payload_json=json.dumps(payload, ensure_ascii=False, indent=2),
    )
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return _parse_gemini_json(response.text)
    except GeminiRateLimitError:
        raise
    except Exception as e:
        _handle_gemini_error(e)
