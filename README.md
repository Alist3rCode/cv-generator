# CV Generator

Application web de génération de CV, développée avec **FastAPI** et **PostgreSQL**, déployable via Docker.

## Installation rapide

```bash
git clone https://github.com/Alist3rCode/cv-generator.git
cd cv-generator
cp .env.example .env   # éditer les valeurs (SECRET_KEY, POSTGRES_PASSWORD, GEMINI_API_KEY…)
docker compose up -d
```

> Voir **[INSTALL.md](INSTALL.md)** pour le guide complet (configuration, backup, mise à jour, dépannage).

## Fonctionnalités

- **Authentification** — Connexion / inscription sécurisée (JWT, cookie httponly)
- **Gestion du profil** — Téléphone, LinkedIn, poste, photo de profil (recadrage 1:1 via Cropper.js), bio multi-langue, langues parlées avec niveau CEFR (A1 → C2 + Langue maternelle)
- **Expériences professionnelles** — Éditeur de texte riche (Quill), dates MM/YYYY, durée calculée, autocomplete localisation, compétences associées
- **Formations** — Diplômes, établissements, ville (autocomplete)
- **Certifications** — Avec dates d'obtention et d'expiration
- **Compétences** — Hard skills et soft skills avec niveau (1 à 4) et famille
- **Import de template Word** — L'admin importe un `.docx` avec des balises `{{BALISE}}`
- **Export CV** — Génération en `.docx` ou `.pdf` à partir du template, historique des exports, indicateur de progression
- **Multi-langue** — Langues configurables depuis l'admin (FR 🇫🇷, EN 🇬🇧, ES 🇪🇸, IT 🇮🇹, DE 🇩🇪 par défaut), ordonnables par drag-and-drop, drapeaux interactifs sur tous les formulaires
- **Dashboard** — Indicateurs (expériences, formations, certifications, hard/soft skills, langues), timeline interactive, donut de complétion (5 critères × 20 %), nuage de compétences animé
- **Auto-save par champ** — Chaque champ a ses propres boutons disquette / reset indépendants ; sauvegarder un champ ne touche pas les autres
- **Duplication de traduction** — Depuis la liste, clic sur une langue non traduite pré-remplit le formulaire depuis une traduction existante ; une bannière globale invite à confirmer l'ensemble avant enregistrement
- **Gestion des traductions** — Pills colorées dans les listes (vert = traduit, grisé = manquant) ; bouton `+` pour créer une traduction, bouton `−` pour en supprimer une (modale de confirmation irréversible)
- **Fonctions IA (Gemini)** — Import de CV PDF/DOCX avec extraction automatique de toutes les données via Google Gemini ; traduction complète du profil vers une langue cible ; formulaire de révision interactif avec boutons 💾/↺ par champ ; avertissement si des données existent déjà, icônes info clignotantes affichant la valeur actuelle en base au survol
- **Configuration IA (admin)** — Clé API, modèle Gemini et activation/désactivation depuis l'interface d'administration ; les prompts restent dans le code
- **Pages d'erreur** — Pages 404 / 500 personnalisées intégrées au thème
- **Sidebar** — Navigation latérale repliable, état mémorisé dans `localStorage`
- **Thème clair / sombre** — Détecte automatiquement la préférence système, toggle dans la sidebar

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| ORM | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) |
| Base de données | PostgreSQL 16 (SQLite en fallback local) |
| Auth | JWT via `python-jose` + `passlib` |
| Templates HTML | Jinja2 + Bootstrap 5.3 |
| Éditeur riche | [Quill.js](https://quilljs.com/) (CDN) |
| Graphique | [Chart.js](https://www.chartjs.org/) (CDN) |
| Timeline | [vis-timeline](https://visjs.github.io/vis-timeline/) (CDN) |
| Drag-and-drop | [SortableJS](https://sortablejs.github.io/Sortable/) (CDN) |
| Recadrage photo | [Cropper.js](https://fengyuanchen.github.io/cropperjs/) (CDN) |
| Autocomplete | [Nominatim / OpenStreetMap](https://nominatim.org/) |
| Génération DOCX | `python-docx` |
| Export PDF | LibreOffice headless *(voir note ci-dessous)* |
| IA — extraction & traduction | [Google Gemini](https://ai.google.dev/) via `google-genai` (SDK officiel) |

## Export PDF

L'export PDF utilise **LibreOffice headless** (inclus dans l'image Docker) pour convertir le `.docx` généré. Aucune installation supplémentaire n'est nécessaire avec Docker.

En local sous Windows, LibreOffice doit être installé sur la machine. Le chemin `C:\Program Files\LibreOffice\program\swriter.exe` est détecté automatiquement.

## Fonctions IA

Les fonctions IA utilisent l'API **Google Gemini** pour :

- **Importer un CV** (PDF ou DOCX) → extraction automatique de toutes les données (expériences, formations, certifications, compétences, langues, bio, profil)
- **Traduire le profil** vers une langue cible → traduction des rubriques sélectionnées en conservant les noms propres d'entreprises

### Configuration

**Option 1 — Variable d'environnement** (fichier `.env`, déjà ignoré par git) :

```env
GEMINI_API_KEY=AIzaSy...votre_clé...
GEMINI_MODEL=gemini-2.0-flash
```

**Option 2 — Interface admin** : Administration → Configuration IA → saisir la clé et activer. La clé est stockée en base et prioritaire sur le fichier `.env`.

Obtenez une clé gratuite sur [Google AI Studio](https://aistudio.google.com/app/apikey).

### Gestion des erreurs de quota (429)

Si le quota Gemini est dépassé, un message clair s'affiche avec un compte à rebours automatique indiquant quand réessayer.

## Installation

> Voir **[INSTALL.md](INSTALL.md)** pour le guide complet.

### Résumé

```bash
git clone https://github.com/Alist3rCode/cv-generator.git
cd cv-generator
cp .env.example .env          # Éditer SECRET_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL, ADMIN_PASSWORD
                              # Optionnel : GEMINI_API_KEY pour les fonctions IA
docker compose up -d          # Build + démarrage (première fois ~5 min)
```

L'application est accessible sur **http://\<IP-serveur\>:9000**

Le compte admin, les tables et les langues par défaut sont créés automatiquement au premier démarrage.

## Structure du projet

```
cv-generator/
├── main.py                  # Point d'entrée FastAPI + handlers d'erreur + filtres Jinja2
├── models.py                # Modèles SQLAlchemy (Language.sort_order, CEFRLevelEnum…)
├── database.py              # Configuration PostgreSQL (DATABASE_URL depuis env)
├── seed.py                  # Données initiales (admin + langues)
├── requirements.txt
│
├── routers/
│   ├── auth.py              # Login / logout / JWT
│   ├── users.py             # Inscription, liste utilisateurs
│   ├── profile.py           # Dashboard + profil + bio + langues parlées + photo
│   ├── experiences.py       # CRUD expériences (multi-langue via GID) + save-skills + delete-translation
│   ├── formations.py        # CRUD formations + delete-translation
│   ├── certifications.py    # CRUD certifications + delete-translation
│   ├── competences.py       # CRUD compétences
│   ├── admin.py             # Admin langues, templates Word, corbeille, configuration IA
│   ├── ai.py                # Import CV via IA + traduction (preview + save)
│   ├── templates.py         # Import templates Word
│   └── exports.py           # Génération, téléchargement et historique des CV
│
├── services/
│   ├── cv_generator.py      # Moteur de génération DOCX/PDF (HTML→Word, balises, tableaux, photo)
│   └── gemini.py            # Client Gemini (extraction CV, traduction, gestion erreurs 429)
│
├── static/
│   ├── style.css            # Styles globaux (sidebar, timeline, pills de traduction…)
│   ├── js/
│   │   └── autosave.js      # Lib auto-save par champ (wrapInput, wrapTextarea, wrapQuill, bindSelect)
│   ├── template_base.docx   # Template Word de base téléchargeable
│   └── favicon.png
│
├── templates/
│   ├── base.html            # Layout principal (sidebar, dark mode, CSS auto-save)
│   ├── macros.html          # Macros Jinja2 (lang_tabs, unsaved_guard)
│   ├── error.html           # Page d'erreur générique (404, 500…)
│   ├── auth/
│   ├── profile/             # dashboard.html (bandeau import IA), edit.html (photo Cropper.js)
│   ├── experiences/         # list.html (pills + modale suppression trad.), form.html
│   ├── formations/          # list.html, form.html
│   ├── certifications/      # list.html, form.html
│   ├── competences/         # list.html, form.html
│   ├── exports/
│   ├── ai/                  # index.html — import CV + traduction + modale de révision
│   └── admin/               # layout.html, languages.html (drag-and-drop), trash.html, ai_config.html
│
├── uploads/                 # Templates Word importés (ignoré par git)
└── exports/                 # CV générés (ignoré par git)
```

## Architecture multi-langue

Tous les contenus traduisibles (expériences, formations, certifications, compétences) utilisent un **GID (Group ID)** — un UUID partagé entre toutes les traductions d'une même entrée.

- La liste affiche une entrée par GID avec des **pills de langue** intégrées dans la carte
- Les pills vertes (traduites) permettent d'éditer la traduction ou de la **supprimer** (bouton `−`)
- Les pills grises (manquantes) permettent de **créer une traduction** (bouton `+`) en pré-remplissant depuis une traduction existante ; si plusieurs langues sources existent, une modale demande laquelle utiliser
- En mode édition, des **onglets drapeaux** permettent de basculer entre les langues
- La **bio** est par utilisateur × langue (pas de GID)
- Les **langues parlées** du profil utilisent les niveaux CEFR : A1, A2, B1, B2, C1, C2, Langue maternelle

### Flux de duplication de traduction

Lorsqu'on ouvre un formulaire pour une langue non encore traduite avec du contenu pré-rempli disponible :

1. Les champs sont remplis **silencieusement** (sans déclencher l'autosave)
2. Une **bannière bleue** s'affiche avec un bouton "Enregistrer cette traduction"
3. L'utilisateur vérifie ou modifie les champs, puis valide **en une seule action**
4. Après enregistrement, la page recharge en mode autosave normal par champ

## Auto-save par champ

Les formulaires d'édition (profil, expériences, formations, certifications, compétences) ne comportent plus de bouton Enregistrer global :

| Type de champ | Comportement |
|---|---|
| Texte 1 ligne | Bouton 💾 (vert) + bouton ↺ (orange) apparaissent à la modification — sauvegarder un champ ne touche pas les autres |
| Textarea / Quill | Colonne ↺ (haut) / 💾 (bas) à droite du bloc |
| Select / dropdown | Sauvegarde automatique au changement de valeur |
| Formulaire de création | Bouton Enregistrer classique conservé (redirect après création) |

## Administration des langues

La page **Admin > Langues** permet de :

- Ajouter / modifier / désactiver des langues
- **Réordonner les langues** par drag-and-drop (colonnes, onglets et pills respectent cet ordre partout dans l'application)
- L'ordre est persisté via le champ `sort_order` en base

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
| `{{PHOTO}}` | Photo de profil (carré 2,5 cm × 2,5 cm) — remplacée par une image inline si uploadée, sinon supprimée |

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
| Auto-save par champ | Chaque champ sauvegarde indépendamment ; un champ enregistré ne provoque pas la sauvegarde des autres |
| Duplication de traduction | Pré-remplissage silencieux + bannière globale de confirmation |
| Pills de traduction | Indicateurs visuels dans les listes ; `+` pour créer, `−` pour supprimer (irréversible) |
| Ordre des langues | Drag-and-drop dans l'admin, propagé à toute l'interface |
| Filtre compétences 100 % | Si toutes les compétences sont traduites dans une langue, un message le signale sans filtrer les cartes |
| Pages d'erreur | 404, 500… affichées dans le thème de l'application |
| Alerte quitter | Pop-up navigateur si des modifications ne sont pas sauvegardées (formulaires de création) |
| Page vide | Listes vides redirigent directement vers le formulaire d'ajout |
| Thème | Détecte la préférence système, toggle dans la sidebar, mémorisé dans `localStorage` |
| Sidebar | Repliable (icônes seules), état persisté dans `localStorage` |
| Autocomplete localisation | Suggestions Nominatim avec navigation clavier sur les champs ville / localisation |
| Picker compétences | Ajout / retrait depuis le formulaire d'expérience, avec création inline et auto-save |
| Historique exports | Les exports sont conservés même si le template associé est supprimé |
| Suppression compétence | Modale listant les expériences impactées avant suppression |
| Corbeille | Les expériences, formations et certifications supprimées passent en corbeille et sont restaurables |
| Photo de profil | Upload, recadrage 1:1 (Cropper.js), prévisualisation temps réel dans la sidebar, suppression avec confirmation |
| Import IA | Profil vide au premier login → bandeau d'invitation à importer un CV |
| Import IA — révision | Modale xl scrollable avec accordion, champs éditables, boutons 💾/↺ par champ avant enregistrement |
| Import IA — données existantes | Modale d'avertissement si le profil contient déjà des données (précise ce qui est remplacé vs ajouté) ; icône info orange clignotante sur chaque champ ayant une valeur en base, avec infobulle au survol |
| Quota IA | Erreur 429 Gemini affichée avec compte à rebours automatique (délai précis extrait de la réponse Gemini) |

## Licence

Projet interne — tous droits réservés.
