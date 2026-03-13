\# Projet Enron Discovery



\## Installation

1\. Installer Docker et Python.

2\. Cloner ce dépôt.

3\. Lancer `docker-compose up -d` pour démarrer PostgreSQL.

4\. Installer les dépendances : `pip install -r requirements.txt` (si tu as créé un fichier requirements.txt).

5\. Appliquer les migrations : `python manage.py migrate`.

6\. Importer les données : `python import.py` (après avoir placé le dossier maildir à la racine).

7\. Démarrer le serveur : `python manage.py runserver`.



\## Choix de modélisation

(explique brièvement tes tables)



Projet Enron Discovery



Description

Ce projet a été réalisé dans le cadre d'un travail d'investigation numérique (e-Discovery). Il exploite le célèbre Enron Email Dataset (plus de 500 000 emails) pour fournir une interface web permettant aux journalistes et auditeurs de :



Naviguer dans les échanges,



Identifier les acteurs clés,



Rechercher des informations critiques,



Visualiser les fils de discussion,



(Optionnel) Analyser les connexions entre collaborateurs.



L'application est construite avec Django et utilise PostgreSQL pour le stockage, avec une recherche plein texte optimisée.



Installation

Prérequis

Python 3.10 ou supérieur



Docker Desktop (pour PostgreSQL) ou PostgreSQL installé localement



Git



Étapes

Cloner le dépôt



bash

git clone https://github.com/votre-utilisateur/enron-discovery.git

cd enron-discovery

Créer et activer un environnement virtuel (optionnel mais recommandé)



bash

python -m venv venv

\# Sous Windows

venv\\Scripts\\activate

\# Sous Linux/Mac

source venv/bin/activate

Installer les dépendances Python



bash

pip install -r requirements.txt

(Si vous n'avez pas encore de fichier requirements.txt, générez-le après installation avec pip freeze > requirements.txt)



Lancer PostgreSQL avec Docker



bash

docker-compose up -d

Le fichier docker-compose.yml fourni crée une base de données nommée enron avec l'utilisateur enron et le mot de passe enron, accessible sur le port 5432.



Appliquer les migrations Django



bash

python manage.py migrate

Importer les données



Placez le dossier maildir (contenant les emails Enron) à la racine du projet, ou modifiez le chemin dans le script import.py.



Exécutez le script d'import (un échantillon est conseillé pour commencer) :



bash

python import.py

L'import complet des 500 000 emails peut prendre plusieurs heures. Pour un test rapide, vous pouvez limiter l'import à un sous-dossier (par exemple allen-p/inbox) en modifiant la variable base dans le script.



Lancer le serveur de développement



bash

python manage.py runserver

Accédez à l'application sur http://127.0.0.1:8000



Choix de modélisation

La base de données a été conçue pour supporter un volume important d'emails tout en permettant des requêtes efficaces. Voici les principales entités et leurs justifications :



Tables principales

Collaborateur (discovery\_collaborateur)



Stocke les adresses email (champ email unique) et éventuellement le nom.



Permet d'identifier de manière unique chaque personne impliquée dans les échanges.



Message (discovery\_message)



Contient les métadonnées : message\_id (identifiant unique de l'email), date, objet, corps.



Une clé étrangère vers Collaborateur (expediteur) lie chaque message à son auteur.



Le champ in\_reply\_to (optionnel) référence le message\_id du message parent, permettant de reconstruire les fils de discussion.



Destinataire (discovery\_message\_destinataires)



Table d'association many‑to‑many entre Message et Collaborateur.



Permet de gérer les multiples destinataires (To, Cc, Bcc) sans duplication des messages.



Une table séparée évite la redondance et normalise le schéma.



Dossier (discovery\_folder) et MessageFolder (discovery\_messagefolder)



Représentent l'arborescence des dossiers telle qu'elle existait dans les boîtes aux lettres originales.



Utiles pour conserver le contexte organisationnel, mais non essentiels pour la recherche.



Pièce jointe (optionnelle) – non implémentée dans cette version.



Optimisations et contraintes

Index :



Index sur date pour accélérer les recherches par période.



Index sur message\_id et in\_reply\_to pour faciliter la construction des threads.



Pour la recherche plein texte, nous prévoyons d'utiliser les index GIN de PostgreSQL sur le champ corps (via SearchVector), ce qui permettra des requêtes efficaces sur le contenu des messages.



Normalisation :



La séparation des entités évite la duplication des adresses email et des messages.



Les clés étrangères avec on\_delete=models.CASCADE garantissent l'intégrité référentielle.



Contraintes d'unicité :



Collaborateur.email est unique.



Message.message\_id est unique (certains emails peuvent être dupliqués dans l'arborescence, on les ignore lors de l'import).



Justification des choix

Le schéma permet de répondre aux exigences du cahier des charges :



Dashboard : agrégations rapides (COUNT, GROUP BY) grâce aux index.



Recherche : la recherche plein texte sera performante avec les index GIN.



Explorateur de threads : la jointure sur in\_reply\_to permet de remonter les réponses.



Graphe d'influence : les tables many‑to‑many facilitent le comptage des interactions entre collaborateurs.



Ce modèle a été testé sur un échantillon de 3000 emails et montre de bonnes performances. Pour l'ensemble du corpus, des optimisations supplémentaires (partitionnement, réglage des index) pourront être envisagées.



