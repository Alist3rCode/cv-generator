# CV Generator

Application web de génération de CV, développée avec **FastAPI** et **SQLite**.

## Fonctionnalités

- **Authentification** — Connexion / inscription sécurisée (JWT, cookie httponly)
- **Gestion du profil** — Téléphone, LinkedIn, bio multi-langue
- **Expériences professionnelles** — Éditeur de texte riche (Quill), dates MM/YYYY, durée calculée, autocomplete localisation
- **Formations** — Diplômes et établissements
- **Certifications** — Avec dates d'obtention et d'expiration
**Compétences** — Hard skills et soft skills avec niveau (1 à 4)
- **Import de template Word** — L'admin importe un `.docx` avec des balises `{{BALISE}}`
- **Export CV** — Génération en `.docx` ou `.pdf` à partir du template
- **Multi-langue** — 5 langues par défaut (FR 🇫🇷, EN 🇬🇧, ES 🇪🇸, IT 🇮🇹, DE 🇩🇪), drapeaux interactifs sur tous les formulaires
- **Dashboard** — Indicateurs (expériences, formations, certifications, hard/soft skills), timeline interactive des expériences, donut de complétion, nuage de compétences animé
- **Sidebar** — Navigation latérale repliable (icônes seules ou avec labels), état mémorisé dans `localStorage`
- **Timeline vis-timeline** — Barres colorées (indigo/jaune), labels externes pour les expériences courtes, années significatives uniquement sur l'axe
- **Nuage de compétences** — Mots flottants animés, taille proportionnelle au poids (niveau × occurrences dans les expériences), hard skills en orange sanguine, soft skills en vert
- **Thème clair / sombre** — Détecte automatiquement la préférence système, toggle dans la sidebar
- **Rôles** — Utilisateur standard / Administrateur par organisation

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) |
| Base de données | SQLite |
| Schémas | [Pydantic v2](https://docs.pydantic.dev/) |
| Auth | JWT via `python-jose` + `passlib` |
| Templates HTML | Jinja2 + Bootstrap 5.3 |
| Éditeur riche | [Quill.js](https://quilljs.com/) (CDN) |
| Graphique | [Chart.js](https://www.chartjs.org/) (CDN) |
| Timeline | [vis-timeline](https://visjs.github.io/vis-timeline/) (CDN) |
| Drapeaux | [flagcdn.com](https://flagcdn.com) (SVG) |
| Autocomplete | [Nominatim / OpenStreetMap](https://nominatim.org/) |
| Génération DOCX | `python-docx` |
| Export PDF | WeasyPrint |

## Installation

### Prérequis

- **Python 3.12** (requis — Python 3.14 non supporté par `pydantic-core`)
- pip

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/Alist3rCode/cv-generator.git
cd cv-generator

# 2. Installer les dépendances
py -3.12 -m pip install -r requirements.txt

# 3. (Optionnel) Créer un compte admin de démo
py -3.12 seed.py

# 4. Lancer l'application
py -3.12 -m uvicorn main:app --reload --port 9000
```

L'application est accessible sur **http://localhost:9000**

> Les 5 langues par défaut (fr, gb, es, it, de) sont créées automatiquement au premier démarrage.

### Compte admin de démo (après `seed.py`)

| Champ | Valeur |
|-------|--------|
| Email | `admin@example.com` |
| Mot de passe | `admin1234` |

> **Important :** Changez ce mot de passe avant toute utilisation en production.

## Structure du projet

```
cv-generator/
├── main.py                  # Point d'entrée FastAPI + filtres Jinja2
├── models.py                # Modèles SQLAlchemy
├── schemas.py               # Schémas Pydantic
├── database.py              # Configuration SQLite
├── seed.py                  # Données initiales (admin + langues)
├── requirements.txt
│
├── routers/
│   ├── auth.py              # Login / logout / JWT
│   ├── users.py             # Inscription, liste utilisateurs
│   ├── profile.py           # Dashboard + profil + bio multi-langue
│   ├── experiences.py       # CRUD expériences (multi-langue via GID)
│   ├── formations.py        # CRUD formations
│   ├── certifications.py    # CRUD certifications
│   ├── competences.py       # CRUD compétences
│   ├── templates.py         # Import templates Word (admin)
│   └── exports.py           # Génération et téléchargement CV
│
├── services/
│   └── cv_generator.py      # Moteur de génération DOCX/PDF
│
├── static/
│   ├── style.css            # Styles globaux (sidebar, timeline, nuage de mots…)
│   └── favicon.png
│
├── templates/
│   ├── base.html            # Layout principal (sidebar repliable, dark mode, autocomplete)
│   ├── macros.html          # Macros Jinja2 (lang_tabs, unsaved_guard)
│   ├── auth/
│   ├── profile/             # dashboard.html, edit.html
│   ├── experiences/
│   ├── formations/
│   ├── certifications/
│   ├── competences/
│   └── exports/
│
├── uploads/                 # Templates Word importés (ignoré par git)
└── exports/                 # CV générés (ignoré par git)
```

## Architecture multi-langue

Tous les contenus traduisibles (expériences, formations, certifications, compétences) utilisent un **GID (Group ID)** — un UUID partagé entre toutes les traductions d'une même entrée.

- La liste affiche une entrée par GID (langue principale)
- En mode édition, des **onglets drapeaux** permettent de basculer entre les langues
- Un onglet clignote si des modifications ne sont pas encore sauvegardées

La **bio** est par utilisateur × langue (pas de GID).

## Comportements UX

| Fonctionnalité | Description |
|---|---|
| Bouton Enregistrer | Passe en bleu (`btn-primary`) si le formulaire a des modifications non sauvegardées |
| Alerte quitter | Pop-up navigateur si vous tentez de quitter une page avec des modifications non sauvegardées |
| Page vide | Expériences / formations / certifications / compétences vides redirigent directement vers le formulaire d'ajout |
| Thème | Détecte la préférence système (clair/sombre), modifiable via la sidebar, mémorisé dans `localStorage` |
| Sidebar | Repliable (icônes seules), état persisté dans `localStorage` |
| Autocomplete localisation | Suggestions Nominatim avec navigation clavier (↑ ↓ Entrée Échap) sur tous les champs de localisation |
| Picker compétences | Ajout/retrait de compétences depuis le formulaire d'expérience, avec création inline |
| Suppression compétence | Modale de confirmation listant les expériences impactées avant suppression |

## Utilisation des templates Word

Créez un fichier `.docx` avec les balises suivantes :

### Balises simples

| Balise | Description |
|--------|-------------|
| `{{NOM}}` | Nom de famille |
| `{{PRENOM}}` | Prénom |
| `{{EMAIL}}` | Adresse email |
| `{{TELEPHONE}}` | Numéro de téléphone |
| `{{LINKEDIN}}` | URL LinkedIn |
| `{{BIO}}` | Texte de présentation |

### Sections répétées (tableaux Word)

Créez un tableau avec une **ligne modèle** — l'application la duplique pour chaque entrée.

**Expériences :** `{{EXP_TITRE}}` `{{EXP_ENTREPRISE}}` `{{EXP_LOCATION}}` `{{EXP_DEBUT}}` `{{EXP_FIN}}` `{{EXP_DUREE}}` `{{EXP_SUMMARY}}` `{{EXP_DESC}}`

**Formations :** `{{FORM_DIPLOME}}` `{{FORM_ETAB}}` `{{FORM_DEBUT}}` `{{FORM_FIN}}`

**Certifications :** `{{CERT_TITRE}}` `{{CERT_ORG}}` `{{CERT_DATE}}` `{{CERT_FIN}}`

**Compétences :** `{{HARD_NOM}}` `{{HARD_NIVEAU}}` · `{{SOFT_NOM}}` `{{SOFT_NIVEAU}}`

## Roadmap

- [ ] Import de CV existant (PDF / Word) via IA
- [ ] Import depuis l'export LinkedIn (ZIP)
- [ ] Traduction automatique des champs
- [ ] Gestion admin des utilisateurs d'une organisation
- [ ] Aperçu CV avant export
- [ ] Support photo de profil
- [ ] Éditeur riche pour les descriptions de formations

## Licence

Projet interne — tous droits réservés.
