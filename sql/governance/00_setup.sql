-- Catalog, schemas and landing volume of the DEC demo.
-- Idempotent. ${catalog} is substituted by dec_demo.governance (dec_dev or dec_prod).

CREATE CATALOG IF NOT EXISTS ${catalog}
COMMENT 'Démo DEC : plateforme data d''une enseigne de bricolage fictive. Données 100 % fictives.';

CREATE SCHEMA IF NOT EXISTS ${catalog}.bronze
COMMENT 'Bronze : données brutes, telles que reçues des systèmes sources (caisse, ERP, CRM, entrepôt).';

CREATE SCHEMA IF NOT EXISTS ${catalog}.silver
COMMENT 'Silver : données nettoyées, typées et contrôlées. Usage : équipes data. Contient des données personnelles masquées.';

CREATE SCHEMA IF NOT EXISTS ${catalog}.gold
COMMENT 'Gold : data products prêts à consommer (Power BI, Genie, analystes). Modèle en étoile, documenté et certifié.';

CREATE SCHEMA IF NOT EXISTS ${catalog}.ops
COMMENT 'Ops : sécurité (table d''habilitations, fonctions de RLS et de masquage), quarantaine qualité et supervision.';

CREATE SCHEMA IF NOT EXISTS ${catalog}.migration
COMMENT 'Migration : sorties des traitements legacy (SAS) et contrôles de réconciliation.';

CREATE VOLUME IF NOT EXISTS ${catalog}.bronze.landing
COMMENT 'Zone de réception des exports des systèmes sources (CSV, JSON, Parquet).';

COMMENT ON VOLUME ${catalog}.bronze.landing IS 'Zone de réception des exports des systèmes sources (CSV, JSON, Parquet).';

ALTER SCHEMA ${catalog}.bronze SET TAGS ('layer' = 'bronze');
ALTER SCHEMA ${catalog}.silver SET TAGS ('layer' = 'silver');
ALTER SCHEMA ${catalog}.gold SET TAGS ('layer' = 'gold');
ALTER SCHEMA ${catalog}.ops SET TAGS ('layer' = 'ops');
ALTER SCHEMA ${catalog}.migration SET TAGS ('layer' = 'migration');
