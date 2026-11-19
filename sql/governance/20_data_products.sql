-- Data product metadata, applied after each pipeline update: domain, ownership,
-- certification and personal-data tags. Comments live in the pipeline definitions.
-- Idempotent. ${catalog} is substituted by dec_demo.governance.
--
-- Certification rule (docs/governance/certification.md): a gold table is tagged
-- certified only if it has an owner, a comment on the table and on every column,
-- quality expectations, and a successful last update.

ALTER MATERIALIZED VIEW ${catalog}.gold.fct_sales SET TAGS (
    'domain' = 'ventes',
    'data_owner' = 'Direction Commerce',
    'data_steward' = 'Contrôle de gestion',
    'technical_owner' = 'Équipe plateforme data',
    'refresh' = 'quotidien',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.gold.fct_stock_weekly SET TAGS (
    'domain' = 'supply',
    'data_owner' = 'Direction Supply Chain',
    'data_steward' = 'Pilotage des approvisionnements',
    'technical_owner' = 'Équipe plateforme data',
    'refresh' = 'hebdomadaire',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.gold.dim_store SET TAGS (
    'domain' = 'référentiel magasins',
    'data_owner' = 'Direction Réseau',
    'technical_owner' = 'Équipe plateforme data',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.gold.dim_product SET TAGS (
    'domain' = 'référentiel produits',
    'data_owner' = 'Direction Offre',
    'technical_owner' = 'Équipe plateforme data',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.gold.dim_customer SET TAGS (
    'domain' = 'client',
    'data_owner' = 'Direction Marketing et Fidélité',
    'technical_owner' = 'Équipe plateforme data',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.gold.dim_date SET TAGS (
    'domain' = 'référentiel temps',
    'data_owner' = 'Équipe plateforme data',
    'contains_pii' = 'false',
    'system.certification_status' = 'certified'
);

ALTER MATERIALIZED VIEW ${catalog}.silver.customers SET TAGS (
    'domain' = 'client',
    'data_owner' = 'Direction Marketing et Fidélité',
    'contains_pii' = 'true'
);

ALTER MATERIALIZED VIEW ${catalog}.silver.customers ALTER COLUMN last_name  -- noqa: PRS
SET TAGS ('pii' = 'nom');
ALTER MATERIALIZED VIEW ${catalog}.silver.customers ALTER COLUMN first_name  -- noqa: PRS
SET TAGS ('pii' = 'prenom');
ALTER MATERIALIZED VIEW ${catalog}.silver.customers ALTER COLUMN email  -- noqa: PRS
SET TAGS ('pii' = 'email');
ALTER MATERIALIZED VIEW ${catalog}.silver.customers ALTER COLUMN phone  -- noqa: PRS
SET TAGS ('pii' = 'telephone');

ALTER MATERIALIZED VIEW ${catalog}.ops.quarantine_sales SET TAGS (
    'domain' = 'qualité',
    'technical_owner' = 'Équipe plateforme data',
    'contains_pii' = 'false'
);
