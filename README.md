# Démo Data Expertise Centre : Databricks + Power BI

Projet de démonstration d'une plateforme data pour une enseigne de bricolage multi-magasins. **Toutes les données sont fictives.**

Il illustre une chaîne complète :

1. ingestion (fichiers, API) ;
2. tables Delta bronze, silver et gold dans un pipeline Lakeflow ;
3. gouvernance Unity Catalog (droits, tags, certification, lineage) ;
4. data products ;
5. modèle sémantique Power BI (PBIP / TMDL) avec RLS ;
6. migration d'un traitement SAS avec réconciliation ;
7. runbooks de support N2 et transfert de compétences.

Stack et versions : [docs/architecture/stack.md](docs/architecture/stack.md).

## Prérequis (macOS)

- Databricks CLI ≥ 1.26 : `brew tap databricks/tap && brew trust --formula databricks/tap/databricks && brew install databricks`
- [uv](https://docs.astral.sh/uv/) (Python 3.12 installé automatiquement)
- Un workspace Databricks Free Edition
- Power BI Desktop sur un poste Windows, pour ouvrir le projet `powerbi/`

## Démarrage

```bash
databricks auth login --host <url-du-workspace> --profile dec-demo
uv sync
uv run pre-commit install
databricks bundle validate
databricks bundle deploy -t dev
```

## Organisation

| Dossier | Contenu |
|---|---|
| `resources/`, `databricks.yml` | Définition du bundle : pipeline, jobs, cibles dev et prod |
| `src/dec_demo_etl/` | Pipeline Lakeflow bronze → silver → gold |
| `src/dec_demo/` | Package Python : générateur de données fictives, ingestion API |
| `sql/governance/` | Objets et droits Unity Catalog |
| `migration/sas/` | Traitement SAS d'origine, version Databricks, réconciliation |
| `powerbi/` | Projet Power BI (PBIP) |
| `docs/` | Architecture, standards de gouvernance, runbooks, templates |
