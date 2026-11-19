-- Gold dimension: customers without any personal data (data minimisation: names, emails
-- and phones stay in silver, masked). ANONYMOUS member for non-identified sales.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.dim_customer (
    customer_id STRING NOT NULL COMMENT 'Identifiant client fidélité (pseudonyme, clé primaire). ANONYMOUS = vente non identifiée.',
    customer_segment STRING COMMENT 'Segment : PRO ou PARTICULIER.',
    home_store_id STRING COMMENT 'Magasin de rattachement.',
    loyalty_since DATE COMMENT 'Date d''adhésion au programme de fidélité.',
    marketing_optin BOOLEAN COMMENT 'Consentement aux communications marketing.',
    CONSTRAINT customer_pk PRIMARY KEY (customer_id)
)
COMMENT 'Dimension Clients sans donnée personnelle (minimisation). Les données nominatives restent en silver, masquées.'
AS SELECT
    customer_id,
    segment AS customer_segment,
    home_store_id,
    loyalty_since,
    marketing_optin
FROM ${catalog}.silver.customers
UNION ALL
SELECT
    'ANONYMOUS' AS customer_id,
    'PARTICULIER' AS customer_segment,
    cast(NULL AS STRING) AS home_store_id,
    cast(NULL AS DATE) AS loyalty_since,
    FALSE AS marketing_optin;
