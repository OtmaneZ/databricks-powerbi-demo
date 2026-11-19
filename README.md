# Démo Data Expertise Centre : Databricks + Power BI

Projet de démonstration d'une plateforme data pour une enseigne de bricolage multi-magasins. **Toutes les données sont fictives.**

La démo illustre une chaîne complète, de la donnée brute au data product gouverné.

| Brique | État |
|---|---|
| Données fictives reproductibles : 40 magasins, 3 000 produits, 60 000 clients, 1,4 M de lignes de ventes, stocks hebdomadaires | Fait |
| Pipeline Lakeflow bronze → silver → gold en SQL : Auto Loader, contrôles qualité, historique des prix en SCD2 (AUTO CDC) | Fait |
| Gouvernance Unity Catalog : RLS par région pilotée par une table d'habilitations, masquage des données personnelles, tags, certification | Fait |
| Data products gold documentés (modèle en étoile), quarantaine qualité, runbook N2 testé | Fait |
| Orchestration : Lakeflow Job déployé par Declarative Automation Bundles (cibles dev et prod) | Fait |
| Modèle sémantique Power BI (PBIP / TMDL) avec RLS | À venir |
| Migration d'un traitement SAS avec réconciliation | À venir |
| Ingestion API, optimisation des performances, cas d'usage IA (Genie) | À venir |

## Documentation

| Document | Contenu |
|---|---|
| [Architecture](docs/architecture/architecture.md) | Flux, couches, modèle en étoile, qualité, sécurité, déploiement |
| [Stack technique](docs/architecture/stack.md) | Versions, noms produits actuels, points vérifiés sur Free Edition |
| [Standards](docs/governance/standards.md) | Nommage, qualité, sécurité, code et déploiement |
| [Certification](docs/governance/certification.md) | Critères et processus de certification d'un data product |
| [Modèle opérationnel](docs/governance/modele-operationnel.md) | Rôles, RACI, niveaux de support, rituels, transfert de compétences |
| [Runbook N2 : prix reçus en centimes](docs/runbooks/incident-n2-prix-en-centimes.md) | Incident rejoué de bout en bout : symptôme, diagnostic, cause, résolution |
| [Fiche data product](docs/templates/fiche-data-product.md) · [Modèle de runbook](docs/templates/runbook-template.md) | Templates réutilisables |

## Prérequis (macOS)

- Databricks CLI ≥ 1.26 : `brew tap databricks/tap && brew trust --formula databricks/tap/databricks && brew install databricks`
- [uv](https://docs.astral.sh/uv/) (Python 3.12 installé automatiquement)
- Un workspace Databricks Free Edition
- Power BI Desktop sur un poste Windows, pour ouvrir le projet `powerbi/`

## Démarrage

```bash
# 1. Authentification (URL du workspace sans chemin, par exemple https://dbc-xxxx.cloud.databricks.com)
databricks auth login --host <url-du-workspace> --profile dec-demo
export DATABRICKS_CONFIG_PROFILE=dec-demo

# 2. Environnement local et contrôles
uv sync
uv run pre-commit install
uv run pytest

# 3. Catalogue, schémas, habilitations, RLS et masques (+ groupes de démo en Free Edition)
uv run python -m dec_demo.governance --catalog dec_dev --files 00_setup.sql 10_security.sql --ensure-groups

# 4. Données fictives : historique jusqu'à septembre 2026
uv run python -m dec_demo.generate --catalog dec_dev --sales-until 2026-09

# 5. Déploiement et exécution complète (gouvernance → pipeline → tags et droits)
databricks bundle deploy -t dev
databricks bundle run dec_demo_platform -t dev
```

Scénario d'incident : `--only-month 2026-10` dépose le mois d'octobre, qui contient l'incident de prix, et `--correct-incident` simule le renvoi corrigé par la source. Le déroulé complet est dans le runbook N2.

## Organisation

| Dossier | Contenu |
|---|---|
| `databricks.yml`, `resources/` | Bundle : cibles dev et prod, pipeline `dec_demo_etl`, job `dec_demo_platform` |
| `src/dec_demo_etl/transformations/` | Pipeline Lakeflow en SQL : `bronze/`, `silver/`, `gold/`, `ops/` |
| `src/dec_demo/` | Générateur de données fictives, exécution des scripts de gouvernance |
| `sql/governance/` | DDL Unity Catalog idempotent : schémas, habilitations, RLS, masques, tags, droits. `target/` : droits cibles par groupes |
| `tests/` | Tests unitaires (dont le garde-fou de la RLS) |
| `migration/sas/` | Traitement SAS d'origine, version Databricks, réconciliation (à venir) |
| `powerbi/` | Projet Power BI PBIP (à venir) |
| `docs/` | Architecture, gouvernance, runbooks, templates |
