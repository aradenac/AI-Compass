# Test Design — prototype UI (révision simplifiée)

Ouvrir `index.html` directement dans Chromium. HTML/CSS/JS autonome, sans serveur ni bibliothèque externe. Données fictives conservées en mémoire.

## Décisions de cette itération

- Suppression des statistiques d’en-tête et du bouton « Réinitialiser la démo ».
- Vue à **deux colonnes** : arbre permanent repliable / liste filtrable à gauche, contenu du Test Design à droite. Aucun panneau latéral de couverture.
- Arbre composé de **catégories dépliables** et de Tasks feuilles ; sélectionner un nœud filtre la liste. La recherche et les filtres de phase, métier et campagne se combinent.
- Test Design lié à une Task existante, avec objectif, entrées, contraintes, résultats attendus, Definition of Done et pièces jointes. Création et édition interactives dans la maquette.
- À la fin de la fiche, **simple liste des campagnes qui incluent le Test Design**, avec le **statut de campagne tel quel**, sans état dérivé ni affichage par AI Solution. Aucune sélection de campagne à inspecter dans le détail.
- **Aucun concept visible de fork, lignée ou version**. Le prototype ne propose ni création de fork ni historique de versions.

## Attention aux spécifications et à la migration

Le contrat Server actuel (`docs/test-cases-server.md`) conserve l’historique immuable et les forks : le choix produit demandé ici les **retire du futur parcours utilisateur**, mais leur suppression physique du backend ne peut pas être inférée. Elle nécessite une décision explicite de migration et de conservation des résultats/campagnes historiques.

Le prototype montre une liste de campagnes/états **fictive**, construite à partir des combinaisons simulées du modèle de campagne. En production, le backend doit fournir des liens authentiques entre Test Case, Task et campagne, avec les statuts réels ; aucun lien ne doit être inféré d'un simple nom. La donnée de couverture par solution demeure dans le Benchmark Workspace, pas dans cette vue. Les modifications du Test Design associé à des campagnes exigent des règles de cohérence historiques et une gestion des références : aucun lien existant ne doit être silencieusement modifié.

Ce prototype n’est pas du code de production et ne modifie pas GitHub.