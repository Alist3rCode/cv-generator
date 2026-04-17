# Installation — CV Generator (Docker)

## Prérequis

- **Docker** ≥ 24 et **Docker Compose** ≥ 2.20 installés sur le serveur Linux
- Port **9000** ouvert sur le pare-feu

Vérification :
```bash
docker --version
docker compose version
```

---

## 1. Télécharger les fichiers de déploiement

Aucun `git clone` nécessaire — télécharger uniquement les deux fichiers requis :

```bash
mkdir cv-generator && cd cv-generator

curl -O https://raw.githubusercontent.com/Alist3rCode/cv-generator/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/Alist3rCode/cv-generator/main/.env.example
```

---

## 2. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

Contenu à personnaliser :

```env
# Clé secrète JWT — OBLIGATOIRE, à changer avant le premier démarrage
SECRET_KEY=<générer avec la commande ci-dessous>

# Mot de passe PostgreSQL — à changer
POSTGRES_PASSWORD=mon-mot-de-passe-securise

# Compte administrateur créé automatiquement au premier démarrage
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=mon-mot-de-passe-admin
```

**Générer une `SECRET_KEY` solide :**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Démarrer l'application

```bash
docker compose up -d
```

Docker va :
1. Télécharger l'image de l'application depuis GitHub Container Registry
2. Télécharger l'image PostgreSQL 16
3. Démarrer la base de données, attendre qu'elle soit prête
4. Démarrer l'application sur le port 9000
5. Créer automatiquement les tables, les langues par défaut et le compte admin

Vérifier que tout tourne :
```bash
docker compose ps
docker compose logs -f app
```

L'application est accessible sur **http://\<IP-du-serveur\>:9000**

---

## 4. Se connecter

Utiliser les identifiants définis dans `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).

> **Important :** Changez le mot de passe admin depuis l'interface après la première connexion.

---

## Gestion courante

### Arrêter / redémarrer
```bash
docker compose down        # Arrêter (données conservées)
docker compose up -d       # Redémarrer
docker compose restart app # Redémarrer uniquement l'application
```

### Voir les logs
```bash
docker compose logs -f         # Tous les services
docker compose logs -f app     # Application seulement
```

### Mettre à jour l'application
```bash
docker compose pull            # Télécharger la dernière image
docker compose up -d           # Redémarrer avec la nouvelle image
```

### Sauvegarder la base de données
```bash
docker compose exec db pg_dump -U cvgen cvgen > backup_$(date +%Y%m%d).sql
```

### Restaurer une sauvegarde
```bash
cat backup_20250101.sql | docker compose exec -T db psql -U cvgen cvgen
```

---

## Structure des données persistées

| Dossier local | Contenu |
|---|---|
| `./data/` | Base de données PostgreSQL |
| `./uploads/` | Templates Word importés |
| `./exports/` | CV générés (Word / PDF) |

Ces dossiers sont créés automatiquement au premier `docker compose up`.  
**Ne pas les supprimer** — ils contiennent toutes les données de l'application.

---

## Dépannage

**L'app ne démarre pas → vérifier les logs :**
```bash
docker compose logs app
```

**PostgreSQL ne répond pas :**
```bash
docker compose logs db
docker compose restart db
```

**Forcer le retéléchargement de l'image :**
```bash
docker compose pull
docker compose up -d --force-recreate
```
