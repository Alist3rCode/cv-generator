# CV Generator

Application web de génération de CV, développée avec **FastAPI** et **SQLite**.

## Fonctionnalités

- **Authentification** — Connexion / inscription sécurisée (JWT, cookie httponly)
- **Gestion du profil** — Téléphone, LinkedIn, poste, bio multi-langue, langues parlées avec niveau CEFR (A1 → C2 + Langue maternelle)
- **Expériences professionnelles** — Éditeur de texte riche (Quill), dates MM/YYYY, durée calculée, autocomplete localisation, compétences associées
- **Formations** — Diplômes, établissements, ville (autocomplete)
- **Certifications** — Avec dates d'obtention et d'expiration
- **Compétences** — Hard skills et soft skills avec niveau (1 à 4) et famille
- **Import de template Word** — L'admin importe un `.docx` avec des balises `{{BALISE}}`
- **Export CV** — Génération en `.docx` ou `.pdf` à partir du template, historique des exports
- **Multi-langue** — 5 langues par défaut (FR 🇫🇷, EN 🇬🇧, ES 🇪🇸, IT 🇮🇹, DE 🇩🇪), drapeaux interactifs sur tous les formulaires
- **Dashboard** — Indicateurs (expériences, formations, certifications, hard/soft skills, langues), timeline interactive, donut de complétion (5 critères × 20 %), nuage de compétences animé
- **Auto-save** — Sauvegarde automatique à la modification : bordure orangée + boutons disquette (vert) et reset (orange) par champ, selects sauvegardés au changement
- **Pages d'erreur** — Pages 404 / 500 personnalisées intégrées au thème
- **Sidebar** — Navigation latérale repliable, état mémorisé dans `localStorage`
- **Thème clair / sombre** — Détecte automatiquement la préférence système, toggle dans la sidebar

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) |
| Base de données | SQLite |
| Auth | JWT via `python-jose` + `passlib` |
| Templates HTML | Jinja2 + Bootstrap 5.3 |
| Éditeur riche | [Quill.js](https://quilljs.com/) (CDN) |
| Graphique | [Chart.js](https://www.chartjs.org/) (CDN) |
| Timeline | [vis-timeline](https://visjs.github.io/vis-timeline/) (CDN) |
| Autocomplete | [Nominatim / OpenStreetMap](https://nominatim.org/) |
| Génération DOCX | `python-docx` |
| Export PDF | LibreOffice headless *(voir note ci-dessous)* |

## Export PDF

> ⚠️ **Non disponible actuellement** — le bouton Export PDF est masqué dans l'interface.

L'export PDF repose sur **LibreOffice headless** pour convertir le `.docx` généré.
Ce n'est pas encore câblé proprement (pas de Dockerfile, pas d'installation automatique).

**Roadmap Docker** : l'objectif est de packager l'application dans un conteneur qui inclut LibreOffice, rendant l'export PDF clef en main sans aucune installation manuelle.

En attendant, sur un serveur Linux :
```bash
sudo apt install libreoffice
```

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
├── main.py                  # Point d'entrée FastAPI + handlers d'erreur + filtres Jinja2
├── models.py                # Modèles SQLAlchemy (CEFRLevelEnum, CEFR_LABELS…)
├── database.py              # Configuration SQLite
├── seed.py                  # Données initiales (admin + langues)
├── requirements.txt
│
├── routers/
│   ├── auth.py              # Login / logout / JWT
│   ├── users.py             # Inscription, liste utilisateurs
│   ├── profile.py           # Dashboard + profil + bio + langues parlées
│   ├── experiences.py       # CRUD expériences (multi-langue via GID) + save-skills
│   ├── formations.py        # CRUD formations
│   ├── certifications.py    # CRUD certifications
│   ├── competences.py       # CRUD compétences
│   ├── templates.py         # Import templates Word (admin)
│   └── exports.py           # Génération, téléchargement et historique des CV
│
├── services/
│   └── cv_generator.py      # Moteur de génération DOCX/PDF (HTML→Word, balises, tableaux)
│
├── static/
│   ├── style.css            # Styles globaux (sidebar, timeline, nuage de mots…)
│   ├── js/
│   │   └── autosave.js      # Lib auto-save (wrapInput, wrapTextarea, wrapQuill, bindSelect)
│   ├── template_base.docx   # Template Word de base téléchargeable
│   └── favicon.png
│
├── templates/
│   ├── base.html            # Layout principal (sidebar, dark mode, CSS auto-save)
│   ├── macros.html          # Macros Jinja2 (lang_tabs, unsaved_guard)
│   ├── error.html           # Page d'erreur générique (404, 500…)
│   ├── auth/
│   ├── profile/             # dashboard.html, edit.html
│   ├── experiences/
│   ├── formations/
│   ├── certifications/
│   ├── competences/
│   ├── exports/
│   └── admin/
│
├── uploads/                 # Templates Word importés (ignoré par git)
└── exports/                 # CV générés (ignoré par git)
```

## Architecture multi-langue

Tous les contenus traduisibles (expériences, formations, certifications, compétences) utilisent un **GID (Group ID)** — un UUID partagé entre toutes les traductions d'une même entrée.

- La liste affiche une entrée par GID (langue principale)
- En mode édition, des **onglets drapeaux** permettent de basculer entre les langues
- La **bio** est par utilisateur × langue (pas de GID)
- Les **langues parlées** du profil utilisent les niveaux CEFR : A1, A2, B1, B2, C1, C2, Langue maternelle

## Auto-save

Les formulaires d'édition (profil, expériences, formations, certifications, compétences) ne comportent plus de bouton Enregistrer global :

| Type de champ | Comportement |
|---|---|
| Texte 1 ligne | Bordure `#d35400` + bouton 💾 (vert) + bouton ↺ (orange) à droite du champ |
| Textarea / Quill | Bordure `#d35400` + colonne ↺ (haut) / 💾 (bas) à droite du champ |
| Select / dropdown | Sauvegarde automatique au changement de valeur |
| Formulaire de création | Bouton Enregistrer classique conservé (redirect après création) |

Le groupe input + boutons forme un bloc continu avec coins arrondis uniquement aux extrémités.

## Génération Word (DOCX)

Le moteur `cv_generator.py` remplace les balises `{{NOM}}` dans le template en préservant la mise en forme Word (couleur, taille, gras…).

### Balises simples

| Balise | Description |
|--------|-------------|
| `{{NOM}}` | Nom de famille |
| `{{PRENOM}}` | Prénom |
| `{{TRIGRAMME}}` | Ex : YLO (1re lettre prénom + 2 premières du nom) |
| `{{EMAIL}}` | Adresse email |
| `{{TELEPHONE}}` | Numéro de téléphone |
| `{{LINKEDIN}}` | URL LinkedIn |
| `{{POSTE}}` | Titre / poste professionnel |
| `{{BIO}}` | Texte de présentation |

### Sections répétées (tableaux Word)

Créez un tableau avec une **ligne modèle** — l'application la duplique pour chaque entrée et supprime les paragraphes devenus vides après fusion.

**Expériences :**
`{{EXP_TITRE}}` `{{EXP_ENTREPRISE}}` `{{EXP_LOCATION}}` `{{EXP_DEBUT}}` `{{EXP_FIN}}` `{{EXP_DUREE}}` `{{EXP_SUMMARY}}` `{{EXP_DESC}}` `{{EXP_HARD_TITRE}}` `{{EXP_HARD_NOM}}` `{{EXP_SOFT_TITRE}}` `{{EXP_SOFT_NOM}}`

> `{{EXP_DESC}}` supporte le HTML Quill (gras, italique, souligné, listes). Placez chaque balise sur sa propre ligne dans le template pour un rendu optimal.

**Formations :**
`{{FORM_DIPLOME}}` `{{FORM_ETAB}}` `{{FORM_VILLE}}` `{{FORM_DEBUT}}` `{{FORM_FIN}}`

**Certifications :**
`{{CERT_TITRE}}` `{{CERT_ORG}}` `{{CERT_DATE}}` `{{CERT_FIN}}`

**Hard skills :**
`{{HARD_NOM}}` `{{HARD_NIVEAU}}` `{{HARD_FAMILLE}}`

**Soft skills :**
`{{SOFT_NOM}}` `{{SOFT_NIVEAU}}` `{{SOFT_FAMILLE}}`

**Langues parlées :**
`{{LNG_NOM}}` `{{LNG_NIVEAU}}`

Un template de base prêt à l'emploi est téléchargeable depuis la page **Templates** de l'interface admin.

## Comportements UX

| Fonctionnalité | Description |
|---|---|
| Auto-save | Sauvegarde par champ sans bouton global (voir section dédiée) |
| Pages d'erreur | 404, 500… affichées dans le thème de l'application |
| Alerte quitter | Pop-up navigateur si des modifications ne sont pas sauvegardées (formulaires de création) |
| Page vide | Listes vides redirigent directement vers le formulaire d'ajout |
| Thème | Détecte la préférence système, toggle dans la sidebar, mémorisé dans `localStorage` |
| Sidebar | Repliable (icônes seules), état persisté dans `localStorage` |
| Autocomplete localisation | Suggestions Nominatim avec navigation clavier sur les champs ville / localisation |
| Picker compétences | Ajout / retrait de compétences depuis le formulaire d'expérience, avec création inline et auto-save |
| Historique exports | Les exports sont conservés même si le template associé est supprimé |
| Suppression compétence | Modale listant les expériences impactées avant suppression |

## Roadmap

- [ ] Import de CV existant (PDF / Word) via IA
- [ ] Traduction automatique des champs via IA
- [ ] Support photo de profil
- [ ] Gestion admin avancée des utilisateurs par organisation
- [ ] Refonte de la gestion des langues pour plus d'ergonomie

## Licence

Projet interne — tous droits réservés.
