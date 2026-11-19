# Stack technique de la démo (état au 18/11/2026)

Les choix ci-dessous ont été vérifiés dans la documentation officielle à la date indiquée. Une mention **NON VÉRIFIÉ** signale un point à tester avant de s'en servir en démo.

## Noms actuels des produits Databricks

Utiliser ces noms dans le code, la documentation et à l'oral. Source : [product-name-changes](https://docs.databricks.com/aws/en/resources/product-name-changes).

| Ancien nom | Nom actuel |
|---|---|
| DLT, Delta Live Tables, Lakeflow Declarative Pipelines | **Lakeflow pipelines** (Spark Declarative Pipelines) |
| Databricks Asset Bundles | **Declarative Automation Bundles** |
| Workflows, Jobs | **Lakeflow Jobs** |
| APPLY CHANGES | **AUTO CDC** |
| Databricks Assistant | **Genie Code** |
| Genie Spaces | **Genie Agents** |
| Databricks One | **Genie One** |
| Lakehouse Monitoring | **Data profiling** (dans Data Quality Monitoring) |
| Vector Search | **AI Search** |

## Choix retenus

| Domaine | Choix | Remarque |
|---|---|---|
| Workspace | Databricks **Free Edition** | Serverless uniquement, 1 SQL warehouse 2X-Small, 1 pipeline actif par type, 5 tâches de job en parallèle, pas de SSO ni de console compte. Usage non commercial. [Limites](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations) |
| CLI | Databricks CLI **v1.26.0** (Homebrew `databricks/tap`) | |
| Déploiement | Declarative Automation Bundles, cibles `dev` et `prod` | Structure calquée sur le template officiel `default-python` (CLI 1.26.0) |
| Python | **3.12**, géré par uv | Imposé par Databricks Connect et par les environnements serverless 3 à 6 |
| Databricks Connect | **18.3.x**, avec `environment_version: "5"` côté jobs | Les deux vont ensemble : on ne change jamais l'un sans l'autre. [Versions serverless](https://docs.databricks.com/aws/en/release-notes/serverless/environment-version/) |
| Pipelines | Lakeflow pipelines, API `from pyspark import pipelines as dp` | `@dp.table`, `@dp.materialized_view`, `@dp.expect*`, `dp.create_auto_cdc_flow`. `import dlt` est l'ancienne API. [Doc Python](https://docs.databricks.com/aws/en/ldp/developer/python-dev) |
| Qualité | Expectations dans le pipeline, anomaly detection (GA 29/10/2026), data profiling | [Data quality monitoring](https://docs.databricks.com/aws/en/data-quality-monitoring/) |
| Ingestion | Auto Loader sur un Volume Unity Catalog, plus une source API | Le connecteur Lakeflow Connect SharePoint est GA depuis le 04/08/2026, mais il demande une app Entra. Il est présenté comme cible, pas en direct. |
| Performance | Liquid clustering `CLUSTER BY AUTO`, predictive optimization, query profile | Le liquid clustering remplace partitionnement et ZORDER. Le « avant » de la démo avant/après peut utiliser l'ancien modèle. [Clustering](https://docs.databricks.com/aws/en/delta/clustering) |
| Gouvernance | GRANT par groupe, COMMENT, tags, lineage, row filters et column masks, certification par le tag `system.certification_status` | ABAC (row filter et mask policies) est GA. [Certification](https://docs.databricks.com/aws/en/data-governance/unity-catalog/certify-deprecate-data) |
| Couche sémantique Databricks | Metric views (GA 02/04/2026) | **Pas consommables par le connecteur Power BI** : le mode de compatibilité BI a été retiré le 17/04/2026. On les montre côté Databricks et Genie. |
| IA | Genie Agents sur les tables gold, AI Functions (`ai_query`, `ai_classify`…) | Genie Agents gratuits jusqu'au 31/01/2027 |
| Migration SAS | Lakebridge **0.15.4** : Analyzer (SAS supporté), puis réécriture manuelle, puis Reconcile Databricks vers Databricks | Lakebridge ne convertit pas le SAS de façon déterministe, et Reconcile ne lit pas le SAS. On charge la sortie SAS legacy en Delta pour la comparer. Lakebridge demande Java 21 ou plus (Java 25 installé). [Analyzer](https://databrickslabs.github.io/lakebridge/docs/assessment/analyzer/) · [Reconcile](https://databrickslabs.github.io/lakebridge/docs/reconcile/) |
| Power BI | PBIP : TMDL pour le modèle, PBIR pour le rapport (format par défaut, GA) | Fichiers édités en texte sur le Mac, ouverts et testés dans Power BI Desktop sur le PC Windows distant, synchronisés par Git |
| Connexion Power BI vers Databricks | Connecteur « Databricks » (driver ADBC par défaut), mode Import et RLS Power BI | **NON VÉRIFIÉ sur Free Edition.** Pas de SSO possible, donc la RLS Unity Catalog ne s'applique pas lecteur par lecteur : la RLS se fait côté Power BI. |
| Copilot Power BI | Hors périmètre en direct | Demande une capacité payante F2+ ou P1+, les capacités d'essai ne suffisent pas |

## Outillage local

| Outil | Usage |
|---|---|
| `powerbi-report-author` v0.5.0 (npm, global) | Validation des fichiers PBIR |
| Extensions VS Code | Databricks, Ruff, TMDL |

## Vérifié sur le workspace Free Edition (19/11/2026)

| Test | Résultat |
|---|---|
| `databricks bundle validate` (cible dev) | OK |
| `CREATE CATALOG dec_dev`, `CREATE SCHEMA` | OK (l'utilisateur est admin du workspace) |
| Table en `CLUSTER BY AUTO` | OK |
| Row filter (`ALTER TABLE … SET ROW FILTER`) | OK, filtrage effectif à la lecture |
| Tags `system.certification_status = certified` et `domain` | OK, visibles dans `information_schema.table_tags` |
| Création de groupe (`databricks groups create`) | OK, mais c'est un groupe **local au workspace** |
| `GRANT … TO <groupe local>` | **Échec** `PRINCIPAL_DOES_NOT_EXIST` : Unity Catalog ne connaît que les groupes de compte |
| `GRANT … TO \`account users\`` | OK |
| API compte (`databricks account …`) | **Indisponible** (pas de console compte sur Free Edition) |
| `is_member('admins')` / `is_account_group_member('admins')` | `true` / `false` : les row filters doivent utiliser `is_member()` pour les groupes locaux |

Conséquences pour la démo :
- Les GRANT par groupe sont écrits pour la cible (groupes de compte synchronisés depuis Entra ID par SCIM) et ne peuvent pas être exécutés tels quels sur Free Edition.
- Les row filters et column masks testent `is_account_group_member(g) OR is_member(g)` : la même fonction marche en cible et sur Free Edition.

Reste à vérifier : la connexion de Power BI Desktop (PC Windows) au SQL warehouse Free Edition.
