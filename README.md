# Projet Enron Discovery

## Description

Ce projet a été réalisé dans le cadre d'un travail d'investigation numérique (e-Discovery). Il exploite le célèbre **Enron Email Dataset** (plus de 500 000 emails) pour fournir une interface web permettant aux journalistes et auditeurs de :

- Naviguer dans les échanges,
- Identifier les acteurs clés,
- Rechercher des informations critiques,
- Visualiser les fils de discussion,
- Analyser les connexions entre collaborateurs.

L'application est construite avec **Django** et utilise **PostgreSQL** pour le stockage, avec une recherche plein texte optimisée.

---

## Fonctionnalités

- **Dashboard** : statistiques globales (nombre d'emails, top 10 des expéditeurs, graphique d'évolution mensuelle, filtre par année).
- **Recherche avancée** : par mots-clés, plage de dates, expéditeur (avec pagination et extrait du corps).
- **Explorateur de threads** : affichage d'un message et de toutes ses réponses avec indentation visuelle (version simple et version complète avec CTE récursive).
- **Graphe d'influence** : pour un collaborateur, liste des personnes avec qui il échange le plus (émissions et réceptions).

---

## Prérequis

- Python 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (pour PostgreSQL) ou PostgreSQL installé localement
- [Git](https://git-scm.com/)

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/votre-utilisateur/enron-discovery.git
cd enron-discovery
```

### 2. Créer et activer un environnement virtuel *(optionnel mais recommandé)*

```bash
python -m venv venv

# Sous Windows
venv\Scripts\activate

# Sous Linux/Mac
source venv/bin/activate
```

### 3. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

> Si vous n'avez pas encore de fichier `requirements.txt`, générez-le après installation avec `pip freeze > requirements.txt`.

### 4. Lancer PostgreSQL avec Docker

```bash
docker-compose up -d
```

Le fichier `docker-compose.yml` fourni crée une base de données nommée `enron` avec l'utilisateur `enron` et le mot de passe `enron`, accessible sur le port `5432`.

### 5. Appliquer les migrations Django

```bash
python manage.py migrate
```

### 6. Importer les données

Placez le dossier `maildir` (contenant les emails Enron) à la racine du projet, ou modifiez le chemin dans le script `import.py`.

Exécutez le script d'import *(un échantillon est conseillé pour commencer)* :

```bash
python import.py
```

> ⚠️ L'import complet des 500 000 emails peut prendre plusieurs heures. Pour un test rapide, vous pouvez limiter l'import à un sous-dossier (par exemple `allen-p/inbox`) en modifiant la variable `base` dans le script.

### 7. Lancer le serveur de développement

```bash
python manage.py runserver
```

Accédez à l'application sur [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Structure du projet

```
enron_project/
├── discovery/                # Application principale
│   ├── management/           # Commandes personnalisées (update_search_vector)
│   ├── migrations/           # Migrations Django
│   ├── templates/            # Templates HTML
│   │   └── discovery/        # Tous les templates de l'application
│   ├── models.py             # Modèles de données
│   ├── views.py              # Vues
│   └── urls.py               # URLs de l'application
├── enron_project/            # Configuration du projet Django
│   ├── settings.py
│   ├── urls.py
│   └── ...
├── data/                     # Dossier pour les données brutes (ignoré par Git)
├── import.py                 # Script d'import des emails
├── manage.py
├── docker-compose.yml        # Configuration Docker pour PostgreSQL
├── requirements.txt          # Dépendances Python
└── README.md
```

---

## Choix de modélisation

### Tables principales

#### `Collaborateur` (`discovery_collaborateur`)

Stocke les adresses email (champ `email` unique) et éventuellement le nom. Permet d'identifier de manière unique chaque personne impliquée dans les échanges.

#### `Message` (`discovery_message`)

Contient les métadonnées : `message_id` (identifiant unique de l'email), `date`, `objet`, `corps`. Une clé étrangère vers `Collaborateur` (`expediteur`) lie chaque message à son auteur. Le champ `in_reply_to` (optionnel) référence le `message_id` du message parent, permettant de reconstruire les fils de discussion. Un champ `search_vector` (`SearchVectorField`) est utilisé pour la recherche plein texte optimisée.

#### `Destinataire` (`discovery_message_destinataires`)

Table d'association many-to-many entre `Message` et `Collaborateur`. Permet de gérer les multiples destinataires (To, Cc, Bcc) sans duplication des messages. Une table séparée évite la redondance et normalise le schéma.

#### `Dossier` (`discovery_folder`) et `MessageFolder` (`discovery_messagefolder`)

Représentent l'arborescence des dossiers telle qu'elle existait dans les boîtes aux lettres originales. Utiles pour conserver le contexte organisationnel, mais non essentiels pour la recherche.

> 📎 *Pièce jointe (optionnelle) — non implémentée dans cette version.*

### Optimisations et contraintes

**Index :**
- Index sur `date` pour accélérer les recherches par période.
- Index sur `message_id` et `in_reply_to` pour faciliter la construction des threads.
- Index GIN sur `search_vector` pour la recherche plein texte.

**Normalisation :**
- La séparation des entités évite la duplication des adresses email et des messages.
- Les clés étrangères avec `on_delete=models.CASCADE` garantissent l'intégrité référentielle.

**Contraintes d'unicité :**
- `Collaborateur.email` est unique.
- `Message.message_id` est unique (certains emails peuvent être dupliqués dans l'arborescence, on les ignore lors de l'import).

### Justification des choix

Le schéma permet de répondre aux exigences du cahier des charges :

| Fonctionnalité | Mécanisme utilisé |
|---|---|
| Dashboard | Agrégations rapides (`COUNT`, `GROUP BY`) grâce aux index |
| Recherche | Recherche plein texte performante avec les index GIN |
| Explorateur de threads | Jointure sur `in_reply_to` pour remonter les réponses |
| Graphe d'influence | Tables many-to-many pour le comptage des interactions |

> Ce modèle a été testé sur un échantillon de 3 000 emails et montre de bonnes performances. Pour l'ensemble du corpus, des optimisations supplémentaires (partitionnement, réglage des index) pourront être envisagées.

---

## Choix techniques

| Composant | Technologie | Justification |
|---|---|---|
| Backend | Django 6.0 | Rapidité de développement, ORM puissant |
| Base de données | PostgreSQL | Index GIN pour la recherche plein texte |
| Recherche plein texte | `SearchVectorField` + `SearchQuery` | Requêtes performantes sur le contenu des messages |
| Conteneurisation | Docker | Isolation de l'environnement PostgreSQL, déploiement facilité |
| Frontend | Bootstrap 5 + Chart.js | Rendu responsive et graphiques interactifs |

---

## Améliorations possibles

- [ ] Ajout d'une authentification pour restreindre l'accès.
- [ ] Mise en place d'un système de cache pour les requêtes fréquentes.
- [ ] Optimisation de l'import avec des traitements parallèles.
- [ ] Utilisation de WebSockets pour des mises à jour en temps réel.