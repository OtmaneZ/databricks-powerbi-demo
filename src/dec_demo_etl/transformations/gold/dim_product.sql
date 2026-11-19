-- Gold dimension: current product catalog (latest SCD2 version) plus an UNKNOWN member
-- for sales lines whose product reference is missing from the catalog.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.dim_product (
    product_id STRING NOT NULL COMMENT 'Référence produit (clé primaire). UNKNOWN = référence absente du catalogue.',
    product_name STRING COMMENT 'Libellé produit.',
    family STRING COMMENT 'Famille : Outillage, Matériaux, Peinture, Plomberie, Électricité, Jardin, Menuiserie, Sanitaire.',
    sub_family STRING COMMENT 'Sous-famille.',
    brand STRING COMMENT 'Marque (marques fictives).',
    current_list_price DECIMAL(12, 2) COMMENT 'Prix catalogue en vigueur.',
    current_unit_cost DECIMAL(12, 2) COMMENT 'Coût d''achat unitaire en vigueur.',
    current_margin_rate DECIMAL(5, 3) COMMENT 'Taux de marge théorique : 1 - coût / prix.',
    price_valid_from TIMESTAMP COMMENT 'Date d''effet du prix en vigueur.',
    CONSTRAINT product_pk PRIMARY KEY (product_id)
)
COMMENT 'Dimension Produits : version courante du catalogue, historique dans silver.products_history.'
AS SELECT
    product_id,
    product_name,
    family,
    sub_family,
    brand,
    cast(list_price AS DECIMAL(12, 2)) AS current_list_price,
    cast(unit_cost AS DECIMAL(12, 2)) AS current_unit_cost,
    cast(1 - unit_cost / list_price AS DECIMAL(5, 3)) AS current_margin_rate,
    __START_AT AS price_valid_from
FROM ${catalog}.silver.products_history
WHERE __END_AT IS NULL
UNION ALL
SELECT
    'UNKNOWN' AS product_id,
    'Produit inconnu (référence absente du catalogue)' AS product_name,
    'Inconnu' AS family,
    'Inconnu' AS sub_family,
    'Inconnu' AS brand,
    cast(NULL AS DECIMAL(12, 2)) AS current_list_price,
    cast(NULL AS DECIMAL(12, 2)) AS current_unit_cost,
    cast(NULL AS DECIMAL(5, 3)) AS current_margin_rate,
    cast(NULL AS TIMESTAMP) AS price_valid_from;
