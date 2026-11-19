# Standards de la plateforme data

Projet de démonstration. Les données sont 100 % fictives.

Ces standards sont volontairement pragmatiques : peu de règles, chacune vérifiable. Ils s'appliquent à tout objet de la plateforme. Une exception est possible, mais elle est écrite dans la pull request et validée par le responsable data governance.

## 1. Nommage

Règles générales :

- Identifiants en anglais, en snake_case, sans accent ni espace.
- Noms toujours complets : `catalog.schema.table`. Dans le code, le catalogue est une variable (`${catalog}`), jamais une valeur en dur.
- `COMMENT` en français, écrits pour un lecteur métier. Commentaires de code en anglais.
- Clés de tags en anglais (`domain`, `data_owner`), valeurs en français (`ventes`, `Direction Commerce`).

| Objet | Règle | Exemples |
|---|---|---|
| Catalogue | `dec_<environnement>` | `dec_dev`, `dec_prod` |
| Schéma | Une couche, liste fermée | `bronze`, `silver`, `gold`, `ops`, `migration` |
| Table bronze | Nom de la source | `bronze.sales`, `bronze.product_price_changes` |
| Table silver | Entité métier au pluriel | `silver.sales`, `silver.customers` |
| Historique SCD2 | Suffixe `_history` | `silver.products_history` |
| Table gold | `dim_` (dimension), `fct_` (fait), grain en suffixe si utile | `gold.dim_store`, `gold.fct_stock_weekly` |
| Fonction de sécurité | `rf_` (row filter), `mask_` (masque de colonne) | `ops.rf_region`, `ops.mask_email` |
| Table ops | Rôle explicite | `ops.security_region_access`, `ops.quarantine_sales` |
| Expectation | Condition attendue | `quantity_positive`, `store_id_present` |
| Motif de quarantaine | Majuscules | `STORE_MISSING`, `PRODUCT_NOT_IN_CATALOG` |
| Groupe | `dec_<rôle>` ou `dec_region_<région>` | `dec_pii_readers`, `dec_region_nord` |
| Ressource de bundle | `dec_demo_<rôle>` | `dec_demo_etl` (pipeline), `dec_demo_platform` (job) |

## 2. Couches : ce qui va où

| Couche | Contenu | Lecteurs | Règles |
|---|---|---|---|
| `bronze` | Données brutes, telles que reçues, avec `_source_file` et `_ingested_at` | Équipe plateforme | Aucune règle métier, aucune suppression |
| `silver` | Données nettoyées, typées, contrôlées, historisées (SCD2 par AUTO CDC) | Équipes data | Expectations obligatoires. Données personnelles masquées |
| `gold` | Data products en modèle en étoile | Power BI, analystes, Genie | Documenté, tagué, certifié. Aucune donnée personnelle |
| `ops` | Habilitations, fonctions de RLS et de masquage, quarantaine qualité | Équipe plateforme, support N2 | Écriture réservée à `dec_platform_admins` |
| `migration` | Sorties des traitements SAS legacy et réconciliation | Équipe plateforme, métier pendant la migration | Temporaire : vidé après décommissionnement du legacy |

- Une vue intermédiaire propre au pipeline reste privée (`TEMPORARY VIEW`, par exemple `sales_enriched`). Elle n'est pas publiée dans le catalogue.
- Nouvelles tables en liquid clustering (`CLUSTER BY AUTO`). Pas de `PARTITIONED BY` ni de `ZORDER`.

## 3. Documentation minimale

| Élément | Bronze | Silver | Gold |
|---|---|---|---|
| `COMMENT` sur la table | Oui | Oui | Oui |
| `COMMENT` sur chaque colonne | Non | Recommandé | **Obligatoire** |
| Clé primaire informative (`PRIMARY KEY`) | Non | Non | Sur les dimensions |
| Tags `domain`, `data_owner`, `technical_owner`, `data_steward`, `refresh`, `contains_pii` | Non | Non | Oui |
| Tag `system.certification_status` | Non | Non | Oui |
| Tag `contains_pii` et tag `pii` par colonne | Non | Si données personnelles | Non (pas de données personnelles) |
| Fiche data product (`docs/templates/fiche-data-product.md`) | Non | Non | Oui |

Les `COMMENT` vivent dans la définition du pipeline. Les tags vivent dans `sql/governance/20_data_products.sql`.

Écart connu de la démo : les dimensions gold n'ont pas encore tous ces tags (il manque `data_steward` et `refresh`, et `technical_owner` sur `gold.dim_date`). Seuls `gold.fct_sales` et `gold.fct_stock_weekly` ont le jeu complet.

Contrôle des colonnes sans commentaire (résultat attendu : aucune ligne) :

```sql
SELECT table_name, column_name
FROM dec_dev.information_schema.columns
WHERE table_schema = 'gold'
  AND table_name NOT LIKE '\_\_%'  -- exclut les tables internes des vues matérialisées
  AND (comment IS NULL OR comment = '');
```

## 4. Qualité des données

| Sévérité | Syntaxe | Quand l'utiliser | Exemples dans la démo |
|---|---|---|---|
| warn | `CONSTRAINT … EXPECT (…)` | Anomalie à suivre, la ligne reste juste et utile | `discount_in_range`, `product_in_catalog` |
| drop | `… ON VIOLATION DROP ROW` | Ligne inexploitable, ou qui fausserait un indicateur | `quantity_positive`, `price_consistent_with_catalog` |
| fail | `… ON VIOLATION FAIL UPDATE` | Défaut massif : publier serait pire que ne rien publier | Aucune règle dans la démo |

Règles :

- Contrôles de structure au plus tôt, en silver. Contrôles de cohérence métier là où le référentiel est disponible (en gold pour le prix comparé au catalogue en vigueur à la date de vente).
- Toute règle drop a une trace : la ligne est listée dans une table de quarantaine `ops.quarantine_<domaine>` avec motif, étape, `is_excluded_from_gold` et `source_file`.
- Un fait réel n'est pas supprimé pour une référence manquante. On le garde avec un membre `UNKNOWN` et une expectation warn.
- Les seuils (par exemple prix unitaire > 1,5 × prix catalogue) sont validés par le data steward et écrits dans la fiche data product.
- Limite actuelle : les lignes en warn sur `discount_in_range` ne sont pas listées en quarantaine. Elles sont visibles uniquement dans les métriques d'expectations.

## 5. Sécurité

- **Moindre privilège.** Les consommateurs lisent `gold` et rien d'autre. `bronze`, `silver` et `ops` sont réservés à l'équipe plateforme. Seule exception : `dec_pii_readers` sur `silver.customers`.
- **GRANT à des groupes, jamais à des utilisateurs nommés.** Cible : groupes de compte synchronisés depuis l'annuaire (`sql/governance/target/30_grants_target.sql`). Free Edition n'a pas de groupes de compte : la démo accorde la lecture de `gold` à `account users` (`sql/governance/30_grants.sql`).
- **Sécurité ligne.** Row filter `ops.rf_region` sur `gold.fct_sales`, `gold.fct_stock_weekly` et `gold.dim_store`. La seule source des habilitations est `ops.security_region_access`. La même table alimentera la RLS Power BI (prévue).
- **Données personnelles.** Minimisation : `gold` n'en contient pas (`gold.dim_customer` sans nom, email ni téléphone). En `silver`, masques `ops.mask_email`, `ops.mask_phone`, `ops.mask_last_name` et tags `pii` par colonne.
- **Fonctions compatibles cible et Free Edition.** Les fonctions testent `is_account_group_member(g) OR is_member(g)`.
- **Toute fonction de sécurité est testée.** Un paramètre ne porte jamais le nom d'une colonne lue dans la fonction : on le préfixe (`row_region`). Voir la leçon ci-dessous.
- **Aucun secret dans le code.** Authentification par profil CLI.

> **Leçon tirée de la démo.** La première version de `ops.rf_region` avait un paramètre nommé `region`, comme la colonne de `ops.security_region_access`. Dans la sous-requête, la colonne masquait le paramètre : la condition `a.region IN (region, '*')` était toujours vraie, et tout membre d'un groupe habilité voyait toutes les régions. Aucune erreur n'a été levée. Correctif : paramètre renommé `row_region`, et le test `test_row_filter_parameter_is_not_shadowed` bloque une régression. C'est pourquoi un test de RLS est obligatoire avant toute mise en production.

## 6. Code et déploiement

- Tout est du code versionné dans Git : pipeline SQL, DDL de gouvernance, job, bundle.
- Une branche par changement, une pull request, une relecture par un pair. Aucune modification manuelle en production via l'interface.
- Avant commit : hooks pre-commit `ruff` et `sqlfluff` (dialecte databricks). Avant pull request : `uv run pytest`.
- Intégration continue qui rejoue ces contrôles : Cible (non implémenté dans la démo).
- Déploiement par Declarative Automation Bundles : `databricks bundle validate`, puis `databricks bundle deploy -t dev`, run et contrôle en dev, puis `-t prod`.
- `dev` : ressources préfixées par utilisateur, planification en pause. `prod` : mode production.
- DDL de gouvernance idempotent : `CREATE … IF NOT EXISTS`, `CREATE OR REPLACE`, `MERGE`.

## 7. Supervision

| Quoi | Où | Qui | Quand |
|---|---|---|---|
| Échec du job `dec_demo_platform` | Notification email `on_failure` du job | Équipe plateforme | À chaque échec |
| Lignes rejetées ou suspectes | `ops.quarantine_sales` | Support N2, data steward | Triage hebdomadaire |
| Taux de rejet par expectation | Interface du pipeline, event log | Équipe plateforme | À chaque run |
| Fraîcheur des data products | Historique des runs du job | Équipe plateforme | Chaque jour |

- Dans la démo, la notification va à l'utilisateur qui déploie. Cible (non implémenté dans la démo) : une liste de diffusion de l'équipe plateforme.
- Tout incident récurrent donne lieu à un runbook (`docs/templates/runbook-template.md`).
