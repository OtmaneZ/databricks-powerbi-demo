-- Ops: quality quarantine for sales. Every line rejected (or kept with a warning) by the
-- pipeline controls, with its reason and source file. Entry point of level-2 support.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.ops.quarantine_sales (
    ticket_id STRING COMMENT 'Numéro de ticket.',
    line_no INT COMMENT 'Numéro de ligne.',
    store_id STRING COMMENT 'Magasin tel que reçu (peut être vide).',
    product_id STRING COMMENT 'Référence produit telle que reçue.',
    sold_at TIMESTAMP COMMENT 'Horodatage de vente tel que reçu.',
    quantity INT COMMENT 'Quantité telle que reçue.',
    unit_price DOUBLE COMMENT 'Prix unitaire tel que reçu.',
    list_price_at_sale DOUBLE COMMENT 'Prix catalogue en vigueur à la date de vente, si connu.',
    quarantine_reason STRING COMMENT 'Motif du rejet ou de l''alerte (voir le runbook N2 pour la liste des motifs).',
    rejected_at STRING COMMENT 'Étape du pipeline qui a détecté l''anomalie.',
    is_excluded_from_gold BOOLEAN COMMENT 'Vrai si la ligne est exclue de gold.fct_sales ; faux si elle y est conservée.',
    source_file STRING COMMENT 'Fichier source (traçabilité jusqu''à l''export d''origine).',
    ingested_at TIMESTAMP COMMENT 'Horodatage d''ingestion en bronze.',
    is_latest_version BOOLEAN COMMENT 'Faux si la ligne a été remplacée par un envoi plus récent (fichier correctif de la source).'
)
COMMENT 'Quarantaine qualité des ventes : lignes rejetées ou suspectes, avec motif et fichier source. Point d''entrée du support N2.'
AS SELECT
    ticket_id,
    line_no,
    store_id,
    product_id,
    to_timestamp(sold_at) AS sold_at,
    quantity,
    unit_price,
    cast(NULL AS DOUBLE) AS list_price_at_sale,
    CASE
        WHEN store_id IS NULL THEN 'STORE_MISSING'
        WHEN quantity IS NULL OR quantity <= 0 THEN 'QUANTITY_NOT_POSITIVE'
        WHEN to_timestamp(sold_at) IS NULL THEN 'SOLD_AT_INVALID'
        ELSE 'UNIT_PRICE_NOT_POSITIVE'
    END AS quarantine_reason,
    'silver.sales' AS rejected_at,
    TRUE AS is_excluded_from_gold,
    _source_file AS source_file,
    _ingested_at AS ingested_at,
    is_latest_version
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY ticket_id, line_no ORDER BY _ingested_at DESC, _source_file DESC)
        = 1 AS is_latest_version
    FROM ${catalog}.bronze.sales
) AS b
WHERE
    store_id IS NULL
    OR quantity IS NULL OR quantity <= 0
    OR to_timestamp(sold_at) IS NULL
    OR unit_price IS NULL OR unit_price <= 0

UNION ALL

SELECT
    ticket_id,
    line_no,
    store_id,
    product_id,
    sold_at,
    quantity,
    unit_price,
    list_price_at_sale,
    CASE WHEN product_known THEN 'PRICE_INCONSISTENT_WITH_CATALOG' ELSE 'PRODUCT_NOT_IN_CATALOG' END AS quarantine_reason,
    'gold.fct_sales' AS rejected_at,
    product_known OR NOT is_latest_version AS is_excluded_from_gold,
    _source_file AS source_file,
    _ingested_at AS ingested_at,
    is_latest_version
FROM sales_enriched
WHERE NOT product_known OR unit_price > list_price_at_sale * 1.5;
