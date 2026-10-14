# Results Explorer — prototype en lecture seule

Ouvrir `index.html` directement dans un navigateur desktop. HTML, CSS et JavaScript sont intégrés, sans dépendance externe.

## Décision de conception (14 octobre 2026)

Results Explorer est **strictement consultatif** : aucune création ou modification d'Evaluation, de Run, de Forecast, de qualification ou de recommandation depuis cette vue. L'onglet « Évaluations enregistrées », les formulaires « Nouvelle évaluation » et les mécanismes de révision éditoriale ont été supprimés du prototype. Cette décision UX ne supprime pas les Evaluations historiques éventuellement conservées dans le backend.

## Structure

- Barre de recherche et filtres par nature de preuve et campagne ; deux orientations de lecture **par Task** / **par solution ou Framework**.
- Tableau avec mesures originelles, statut DoD pour les Runs et confiance explicitement théorique pour les Forecasts.
- Panneau de détails à droite : données mesurées, identification, campagne, méthode, notes, limitations, lien vers la source avec droits.
- Message discret expliquant le passage **automatique des configurations avec preuves publiées, acceptées et qualifiées** vers les **candidates de AI Solutions**. Les critères de qualification restent à formaliser dans le domaine ; l'exemple n'affirme pas qu'ils sont déjà calculés. Seul AI Solutions gère notes éditoriales, complétude des guides, décision de publication et visibilité ingénieur.
- Runs composites affichés séparément et jamais réattribués aux solutions participantes. Unknown ≠ zero. Forecast ≠ measured Run. Échec DoD ≠ absence d'exécution.

## Contrats backend et limites

S'appuie conceptuellement sur `docs/results-explorer-evaluations-server.md`, `docs/individual-benchmark-runs-server.md`, `docs/composite-benchmark-runs-server.md` et les spécifications de recommandations. Aucun score global, classement ou seuil d'admission n'est inventé. Définir l'éligibilité automatisée dans un futur contrat métier avant implémentation ; conserver des décisions éditoriales et droits de publication explicites. Les données de ce fichier sont exclusivement des exemples fictifs.

Validation attendue : revue visuelle 1366×900 et 1024px, filtres et sélection clavier, séparation des types de preuves, autorisation des sources et garantie de lecture seule côté API.