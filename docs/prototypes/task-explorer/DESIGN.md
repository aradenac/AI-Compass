# Task Explorer — prototype de conception

Prototype autonome `index.html`, sans service externe et sans données serveur. **Ne pas confondre avec un schéma backend existant.**

## Décisions explorées

- L'arbre permanent possède deux types d'objets : **catégories internes** et **tâches feuilles seulement**. Les tâches ne peuvent jamais avoir d'enfants ; glisser une tâche dans une catégorie change son parent, sans changer ses labels.
- Les dimensions transverses sont **multi-valuées et cumulables** : phase projet (RFQ / Architecture / Design / Qualification / Maintenance), métier/spécialité (Software, Embedded, Linux, Hardware, etc.), labels transverses. D'autres familles peuvent être créées.
- Les catégories de l'arbre et les familles de labels sont **deux structures indépendantes**. Catégories de l'arbre hiérarchiques ; familles de labels modifiables. Une tâche est localisée dans une catégorie permanente et peut correspondre à plusieurs valeurs de chaque famille de labels.
- En fiche : nom, description, estimation originale du temps humain en heures, pièces jointes, classification, relations contextuelles. Estimation ≠ résultat mesuré, ≠ gain économique calculé.
- La projection « Par labels » présente des vues alternatives sur **les mêmes tâches**, sans dupliquer leurs identifiants ni les déplacer.
- Édition de catégories avec prévention de cycles ; suppression refusée si catégorie non vide. Glisser-déposer autorisé uniquement pour des tâches vers des catégories. Les interactions sont simulées en mémoire, sans persistance.

## Points nécessitant décision d'architecture avant implémentation

- Schéma / versionnement des familles de labels et des valeurs, leur gouvernance et les permissions d'édition ; catégories structurelles versus taxonomie de Tasks déjà existante.
- Cardinalités exactes et contraintes référentielles, fusion/retrait des labels avec migrations non destructrices.
- Historique immuable des modifications et conflits de révision (HTTP 409), pièces jointes par EvidenceBlob autorisé et préservation des références de Campaign, Test Case, Run et Recommendation.
- Portée de l'estimation humaine originale : valeur absolue, unité, provenance et date de référence ; absence de confusion avec DAP et coûts.
- Toute extension métier doit conserver les identifiants publics, les forks versionnés et les liens historiques.

## Validation proposée

Tester la navigation clavier, 1366 × 900 et 1024 px, filtrage multi-axes, conservation des tâches-feuilles, drag/drop, édition labels et fiche. Une validation visuelle réelle doit précéder l'intégration. Aucune modification du dépôt GitHub n'est incluse dans cette livraison.