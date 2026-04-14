# CV Generator

Application web de génération de CV, développée avec **FastAPI** et **SQLite**.

## Fonctionnalités

- **Authentification** — Connexion / inscription sécurisée (JWT)
- **Gestion du profil** — Saisie et modification des informations personnelles
- **Expériences professionnelles** — Ajout, modification, suppression
- **Formations** — Diplômes et établissements
- **Certifications** — Avec dates d'obtention et d'expiration
- **Compétences** — Hard skills et soft skills avec niveau (1 à 4)
- **Import de template Word** — L'admin importe un `.docx` avec des balises
- **Export CV** — Génération en `.docx` ou `.pdf` à partir du template
- **Multi-langue** — Architecture prête pour le support multi-langue (traduction à venir)
- **Rôles** — Utilisateur standard / Administrateur par organisation

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) |
| Base de données | SQLite (développement) |
| Schémas | [Pydantic v2](https://docs.pydantic.dev/) |
| Auth | JWT via `python-jose` + `passlib` |
| Templates HTML | Jinja2 + Bootstrap 5 |
| Génération DOCX | `python-docx` |
| Export PDF | WeasyPrint |

## Installation

### Prérequis

- Python **3.12** (requis — Python 3.14 non supporté par certaines dépendances)
- pip

### Étapes

```bash
# 1. Cloner le dépôt
git clone https://github.com/Alist3rCode/cv-generator.git
cd cv-generator

# 2. Installer les dépendances
py -3.12 -m pip install -r requirements.txt
py -3.12 -m pip install "bcrypt==4.0.1"

# 3. Initialiser la base de données et créer les données initiales
py -3.12 seed.py

# 4. Lancer l'application
py -3.12 -m uvicorn main:app --reload
```

L'application est accessible sur **http://localhost:8000**

### Compte admin par défaut

| Champ | Valeur |
|-------|--------|
| Email | `admin@example.com` |
| Mot de passe | `admin1234` |

> Pensez à changer ce mot de passe en production !

## Structure du projet

```
cv-generator/
├── main.py                  # Point d'entrée FastAPI
├── models.py                # Modèles SQLAlchemy (BDD)
├── schemas.py               # Schémas Pydantic (validation)
├── database.py              # Configuration SQLite
├── seed.py                  # Données initiales (admin + langues)
├── requirements.txt
│
├── routers/                 # Endpoints par domaine
│   ├── auth.py              # Login / logout / JWT
│   ├── users.py             # Inscription, liste utilisateurs
│   ├── profile.py           # Dashboard + profil personnel
│   ├── experiences.py       # CRUD expériences
│   ├── formations.py        # CRUD formations
│   ├── certifications.py    # CRUD certifications
│   ├── competences.py       # CRUD compétences
│   ├── templates.py         # Import templates Word (admin)
│   └── exports.py           # Génération et téléchargement CV
│
├── services/
│   └── cv_generator.py      # Moteur de génération DOCX/PDF
│
├── templates/               # Pages HTML (Jinja2 + Bootstrap 5)
│   ├── base.html
│   ├── auth/
│   ├── profile/
│   ├── experiences/
│   ├── formations/
│   ├── certifications/
│   ├── competences/
│   ├── admin/
│   └── exports/
│
├── static/
│   └── style.css
│
├── uploads/                 # Templates Word importés (ignoré par git)
└── exports/                 # CV générés (ignoré par git)
```

## Utilisation des templates Word

Pour créer un template CV, créez un fichier `.docx` avec les balises suivantes :

### Balises simples (texte)

| Balise | Description |
|--------|-------------|
| `{{NOM}}` | Nom de famille |
| `{{PRENOM}}` | Prénom |
| `{{EMAIL}}` | Adresse email |
| `{{TELEPHONE}}` | Numéro de téléphone |
| `{{LINKEDIN}}` | URL LinkedIn |
| `{{BIO}}` | Texte de présentation |

### Sections répétées (tableaux Word)

Créez un tableau avec **une ligne modèle** contenant les balises — l'application dupliquera cette ligne pour chaque entrée.

**Expériences :**
`{{EXP_TITRE}}` `{{EXP_ENTREPRISE}}` `{{EXP_LOCATION}}` `{{EXP_DEBUT}}` `{{EXP_FIN}}` `{{EXP_SUMMARY}}` `{{EXP_DESC}}`

**Formations :**
`{{FORM_DIPLOME}}` `{{FORM_ETAB}}` `{{FORM_DEBUT}}` `{{FORM_FIN}}`

**Certifications :**
`{{CERT_TITRE}}` `{{CERT_ORG}}` `{{CERT_DATE}}` `{{CERT_FIN}}`

**Compétences :**
`{{HARD_NOM}}` `{{HARD_NIVEAU}}` · `{{SOFT_NOM}}` `{{SOFT_NIVEAU}}`

## Roadmap

- [ ] Import de CV existant (PDF / Word) via IA
- [ ] Traduction automatique des champs via IA
- [ ] Gestion admin des utilisateurs d'une organisation
- [ ] Aperçu CV avant export
- [ ] Support photo de profil

## Licence

Projet interne — tous droits réservés.
