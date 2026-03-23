# Enron Discovery

**Plateforme d'investigation numérique (e-Discovery) — M1 Data Science — Université d'Angers — 2026**

Réalisé par **Danièle Isabelle Nana Fotzeu** et **Mawaki Kahon**

---

## Présentation

**Enron Discovery** est une application web permettant aux journalistes et auditeurs d'explorer le célèbre *Enron Corpus* — plus de 500 000 emails échangés par les cadres d'Enron avant le scandale financier de 2001.

L'application permet de :

- Naviguer dans les échanges par dossiers, expéditeurs et destinataires
- Visualiser des statistiques globales (volume, top acteurs, évolution temporelle)
- Effectuer des recherches avancées (plein texte, filtres par dates, expéditeur, destinataire)
- Explorer les fils de discussion complets
- Analyser les relations d'influence via un graphe interactif

---

## Stack technique

| Composant | Technologie | Justification |
|---|---|---|
| Backend | Django 6.0 (Python 3.12) | Rapidité de développement, ORM puissant |
| Base de données | PostgreSQL 15 | Index GIN natif pour le Full-Text Search |
| Recherche plein texte | `SearchVectorField` + `SearchQuery` | Requêtes performantes sur le contenu des messages |
| Frontend | Bootstrap 5, Chart.js, vis.js, Select2 | Interface responsive et graphiques interactifs |
| Conteneurisation | Docker + docker-compose | Isolation de l'environnement, déploiement facilité |
| Versionnement | Git | Commits atomiques, README, .gitignore |

---

## Prérequis

- Python 3.12 ou supérieur
- Docker et Docker Compose
- Git

---

## Installation

### 1. Cloner le dépôt
```bash
git clone https://github.com/Daniele-Nana/enron-discovery.git
cd enron-discovery
```

### 2. Créer et activer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 3. Installer les dépendances Python
```bash
pip install -r requirements.txt
```

### 4. Démarrer PostgreSQL avec Docker
```bash
docker-compose up -d
```

> Le conteneur crée une base `enron` avec l'utilisateur `enron` (mot de passe `enron`), accessible sur le port `5432`. Les données sont persistées dans un volume Docker.

### 5. Appliquer les migrations Django
```bash
python manage.py migrate
```

### 6. Importer le corpus Enron

Placez le dossier `maildir/` (contenant les emails) à la racine du projet, puis exécutez :
```bash
python import.py
```

> ⚠️ L'import complet des 500 000 emails peut prendre plusieurs heures. Pour un test rapide, limitez l'import à un sous-dossier (ex. `allen-p/inbox`) en modifiant la variable `base` dans le script.

### 7. Lancer le serveur de développement
```bash
python manage.py runserver
```

L'application est accessible à l'adresse **http://127.0.0.1:8000/**.

---

## Fonctionnalités

| URL | Description |
|---|---|
| `/` | Tableau de bord — statistiques globales, top acteurs, évolution mensuelle |
| `/search/` | Recherche avancée plein texte avec filtres et surbrillance |
| `/thread/<id>/` | Fil de discussion — message et réponses directes |
| `/thread_complet/<id>/` | Fil complet depuis la racine (CTE récursive) |
| `/influence/<id>/` | Page d'influence d'un collaborateur |
| `/collaborateur/<id>/tous-emails/` | Tous les emails envoyés/reçus (paginés) |
| `/collaborateur/<id>/dossiers/` | Arborescence des dossiers |
| `/graphe/` | Graphe d'influence interactif |

---

## Structure du projet
```
enron-discovery/
├── discovery/                # Application principale
│   ├── management/           # Commandes personnalisées (update_search_vector)
│   ├── migrations/           # Migrations Django (versionnées)
│   ├── templates/            # Templates HTML (Bootstrap 5)
│   ├── models.py             # Modèles SQL
│   ├── views.py              # Vues Django
│   └── urls.py
├── enron_project/            # Configuration du projet Django
│   ├── settings.py
│   └── urls.py
├── maildir/                  # (à placer) données Enron — non versionné
├── import.py                 # Script d'import des emails
├── docker-compose.yml        # PostgreSQL 15 isolé
├── requirements.txt          # Dépendances Python
├── manage.py
└── README.md
```

---

## Modélisation SQL (MLD)
```
Collaborateur(id PK, email UNIQUE, nom)
     |1
     |N
  Message(id PK, message_id UNIQUE, date, objet, corps,
          expediteur_id FK→Collaborateur, in_reply_to, search_vector)
     |N                        |N
     |                          M
  MessageFolder           Destinataire(message_id FK, collaborateur_id FK)
     |M
  Folder(id PK, path UNIQUE, parent_id FK→Folder  [récursif])
```

### Tables principales

**`Collaborateur`** — Stocke les adresses email (champ `email` unique) et éventuellement le nom. Table dédiée pour éviter toute duplication : un même acteur peut être expéditeur ou destinataire dans plusieurs messages.

**`Message`** — Cœur du système. Contient `message_id` (unique), `date`, `objet`, `corps`, une clé étrangère `expediteur_id` vers `Collaborateur`, le champ `in_reply_to` pour reconstruire les fils, et `search_vector` pour la recherche plein texte.

**`Destinataire`** — Table d'association ManyToMany entre `Message` et `Collaborateur`. Représente fidèlement les champs To, Cc et Bcc sans dupliquer les messages.

**`Folder` et `MessageFolder`** — Conservent l'arborescence des dossiers originaux (inbox, sent…). La clé étrangère récursive `parent_id` permet de reconstituer la hiérarchie.

### Index

| Index | Type | Colonne(s) | Utilité |
|---|---|---|---|
| `idx_search_gin` | GIN | `search_vector` | Recherche plein texte |
| `idx_date` | B-tree | `date` | Filtres et tris temporels |
| `idx_expediteur` | B-tree | `expediteur_id` | Jointures par expéditeur |
| `idx_in_reply_to` | B-tree | `in_reply_to` | Reconstruction des fils |
| `idx_dest` | B-tree | `collaborateur_id` (M2M) | Requêtes sur destinataires |

### Justification des choix

| Fonctionnalité | Mécanisme utilisé |
|---|---|
| Dashboard | Agrégations (`COUNT`, `TruncMonth`) accélérées par les index |
| Recherche | Full-Text Search avec index GIN et `SearchQuery` (websearch) |
| Explorateur de threads | Jointure sur `in_reply_to` + CTE récursive `WITH RECURSIVE` |
| Graphe d'influence | Comptage des interactions via la table ManyToMany |

### Contraintes d'intégrité

- `Collaborateur.email` est unique
- `Message.message_id` est unique (les doublons sont ignorés à l'import)
- Clés étrangères avec `on_delete=CASCADE` pour garantir l'intégrité référentielle
- Contrainte d'unicité sur le couple `(message, folder)` dans `MessageFolder`

---

## Notes techniques

- **Recherche plein texte** : opérateur `websearch` de PostgreSQL (guillemets pour phrase exacte, `-` pour exclure, `OR` pour l'union). Le `search_vector` est alimenté par un trigger PostgreSQL pondérant l'objet (poids `A`) et le corps (poids `B`). Les résultats sont classés par `SearchRank`.
- **Fils de discussion** : deux vues — récursion Python pour les réponses directes, requête `WITH RECURSIVE` (CTE) pour reconstituer tout l'arbre en une seule requête SQL.
- **Cache** : données du dashboard et du graphe d'influence mises en cache en mémoire pendant 1 heure.
- **Import** : insertions via `bulk_create` par lots dans des transactions `atomic()` pour garantir l'intégrité en cas d'erreur.

> ⚠️ La base de données n'est pas incluse dans le dépôt Git (voir `.gitignore`).

---

## Améliorations possibles

- [ ] Authentification pour restreindre l'accès
- [ ] Traitements parallèles pour accélérer l'import
- [ ] Gestion complète des pièces jointes
- [ ] Déploiement en ligne (Render, Railway)

---

## Licence

Projet réalisé dans le cadre d'un travail universitaire — Université d'Angers, 2026.  
Toute reproduction est soumise à l'autorisation des auteurs.

---

*Source des données : [Enron Email Dataset (CMU)](https://www.cs.cmu.edu/~enron/)*
