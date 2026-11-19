-- Silver: loyalty customers. Personal data stays in silver, masked by Unity Catalog
-- column masks for anyone outside dec_pii_readers. Gold never exposes it (data minimisation).

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.customers (
    customer_id STRING COMMENT 'Identifiant client fidélité.',
    first_name STRING COMMENT 'Prénom (donnée personnelle fictive).',
    last_name STRING COMMENT 'Nom (donnée personnelle, masquée hors dec_pii_readers).'
    MASK ${catalog}.ops.mask_last_name,
    email STRING COMMENT 'Email (donnée personnelle, masquée hors dec_pii_readers).'
    MASK ${catalog}.ops.mask_email,
    phone STRING COMMENT 'Téléphone (donnée personnelle, masquée hors dec_pii_readers).'
    MASK ${catalog}.ops.mask_phone,
    segment STRING COMMENT 'Segment : PRO ou PARTICULIER.',
    home_store_id STRING COMMENT 'Magasin de rattachement.',
    loyalty_since DATE COMMENT 'Date d''adhésion au programme de fidélité.',
    marketing_optin BOOLEAN COMMENT 'Consentement aux communications marketing.',
    CONSTRAINT customer_id_present EXPECT (customer_id IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT email_well_formed EXPECT (email RLIKE '^[^@]+@[^@]+\\.[a-z]{2,}$'),
    CONSTRAINT segment_known EXPECT (segment IN ('PRO', 'PARTICULIER'))
)
COMMENT 'Clients fidélité nettoyés. Données personnelles masquées par Unity Catalog (column masks).'
AS SELECT
    customer_id,
    first_name,
    last_name,
    lower(email) AS email,
    phone,
    segment,
    home_store_id,
    loyalty_since,
    marketing_optin
FROM ${catalog}.bronze.customers
QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY _ingested_at DESC) = 1;
