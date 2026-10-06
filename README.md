# Vireel.app - README unique

Ce fichier centralise l'information qui etait auparavant repartie dans plusieurs documents Markdown du projet.

## Vue d'ensemble

Vireel.app est une plateforme de creation video assistee par IA avec trois axes principaux:

- **Clip Generator**: transforme des videos longues en clips courts (Reels/Shorts/TikTok).
- **AI Shorts Creator**: pipeline de creation UGC automatisee.
- **YouTube Studio**: aide a generer titres, miniatures et descriptions optimises.

Le projet est structure autour d'un backend Python/FastAPI, d'un dashboard React/Vite, d'un service de rendu et d'integrations cloud/IA.

## Composants du projet

- `app.py`: API principale et orchestration des jobs backend.
- `main.py`: traitement video, decoupage, analyse et generation de clips.
- `job_manager.py`: cycle de vie des jobs, progression, erreurs, retry.
- `billing.py`: estimation des couts et conversion credits.
- `subtitles.py`, `hooks.py`, `thumbnail.py`, `editor.py`: modules media (sous-titres, overlays, miniatures, edition).
- `supabase_request.py`, `supabase_media.py`: acces data Supabase.
- `s3_uploader.py`: upload, suppression et URL signees S3.
- `dashboard/`: UI utilisateur (React/Vite/Tailwind).
- `render-service/` et `remotion/`: rendu video web/service.
- `supabase/migrations/`: migrations base de donnees.

## Fonctionnalites principales

### Backend

- Gestion de jobs asynchrones avec priorites et retries.
- Generation de clips avec metadata et persistance media.
- Generation et burn de sous-titres.
- Gestion de credits et couts d'operation.
- Persistance projets/reels/captions et historique.
- Integrations stockage S3 + base Supabase.

### Dashboard

- Parcours de creation de reels/sous-titres.
- Parametrage (style sous-titres, options publication, comptes sociaux).
- Visualisation d'etat des jobs et contenus generes.

### IA / Media

- Analyse et suggestions IA (selon fournisseur configure).
- Generation d'assets (thumbnails, hooks, descriptions).
- Outils de rendu video et post-traitement FFmpeg.

## Configuration

La configuration repose principalement sur les variables d'environnement.

Exemples de familles de variables:

- Secrets application (`SECRET_KEY`, etc.)
- Supabase (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, tables)
- AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`, region)
- IA (`GEMINI_API_KEY`, modeles, autres providers)
- Facturation/credits (prix unitaires, majoration)
- Limites operationnelles (duree max, timeouts)
- Retention des medias (voir ci-dessous)

Variables requises au demarrage du backend (l'app refuse de demarrer si elles sont absentes, hors execution des tests) :

- `SUPABASE_JWT_SECRET` : secret JWT du projet Supabase (Project Settings -> API -> JWT Secret), utilise pour verifier les tokens de session envoyes par le frontend (`Authorization: Bearer ...`). C'est la seule source de verite pour l'identite d'un utilisateur cote backend.
- `ENCRYPTION_KEY` : cle (16 caracteres minimum) utilisee pour chiffrer (AES-256-GCM) les tokens OAuth des reseaux sociaux stockes en base.
- `RENDER_SERVICE_API_KEY` : cle interne partagee entre le backend et le render-service (Remotion), verifiee sur chaque appel a `/render`. A definir aussi dans l'environnement du service `renderer` (docker-compose).

### Retention des medias

Vireel ne vend plus de quota de stockage (en Go) a l'utilisateur -- seuls les
credits sont factures. En interne, chaque media (source importe ou produit
genere) a neanmoins une duree de conservation physique en S3, fixee
*definitivement* au moment de sa creation selon le statut d'abonnement de
l'utilisateur a cet instant precis (un changement ulterieur d'abonnement ou
de ces variables n'affecte jamais un media deja cree). Voir `retention_config.py`
pour la validation au demarrage (valeurs negatives/incoherentes refusees) et
`app.py` pour les 3 traitements automatiques (expiration, notification avant
expiration, nettoyage des fichiers temporaires).

Variables (voir `.env.example` pour les valeurs par defaut) :

- `RETENTION_FREE_SOURCE_DAYS` / `RETENTION_FREE_PRODUCED_DAYS` : duree de
  conservation (source / produit) sans abonnement actif.
- `RETENTION_SUBSCRIBER_SOURCE_DAYS` / `RETENTION_SUBSCRIBER_PRODUCED_DAYS` :
  duree de conservation (source / produit) avec abonnement actif.
- `RETENTION_TEMP_FILES_HOURS` : duree de vie des fichiers de travail locaux
  (frames/chunks FFmpeg, uploads, dossiers de job termines) -- une categorie
  distincte, sans lien avec les durees ci-dessus.
- `RETENTION_NOTIFICATION_HOURS_BEFORE` : delai d'avertissement avant la
  suppression automatique d'un media produit (jamais pour un media source).
- `S3_STORAGE_COST_PER_GB_DAY` : cout interne S3/Go/jour utilise pour
  calculer le cout de retention ajoute a la facturation en credits (jamais
  affiche separement a l'utilisateur).

## Lancement local

### Backend (racine)

```zsh
pip install -r requirements.txt
python app.py
```

### Dashboard

```zsh
cd dashboard
npm install
npm run dev
```

### Option Docker Compose

```zsh
docker-compose up --build
```

## Tests

### Backend (pytest)

```zsh
pytest
```

### Dashboard (vitest)

```zsh
cd dashboard
npm test
```

Des tests unitaires ont ete ajoutes sur les modules backend critiques et sur les utilitaires UI `dashboard/src/lib`.

## Deploiement

Le repo contient des fichiers de compose pour differents environnements:

- `docker-compose.yml`
- `docker-compose.staging.yml`
- `docker-compose.prod.yml`

Verifier les variables d'environnement et les migrations Supabase avant mise en production.

La migration `supabase/migrations/20261012_media_lifecycle_and_storage_quota_removal.sql`
supprime `abonnement.stockage` et cree la table `media_assets` (registre du
cycle de vie physique des medias -- voir la section "Retention des medias"
ci-dessus). Aucun media historique n'est retroactivement rattache a cette
table par cette migration (aucune DML de backfill) : un media cree avant son
application n'a simplement pas de ligne `media_assets` et n'est donc jamais
selectionne par les traitements d'expiration/notification -- un backfill
delibere reste a faire separement si souhaite.

## Notes et limites

- Certaines integrations externes (IA, S3, Supabase, reseaux sociaux) necessitent des credentials valides.
- Les performances dependent des ressources machine et de la nature des medias.
- Les workflows AI/UGC evoluent par iteration et peuvent necessiter des ajustements metier.

## Historique de consolidation

Ce README remplace les anciens fichiers Markdown de suivi, checklists, guides et notes de travail pour simplifier la maintenance documentaire.
