-- Gold dimension: stores. Same row filter as the facts, so that slicers only list the
-- stores a user is entitled to.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.dim_store (
    store_id STRING NOT NULL COMMENT 'Identifiant magasin (clé primaire).',
    store_name STRING COMMENT 'Nom du magasin.',
    city STRING COMMENT 'Ville d''implantation.',
    region STRING COMMENT 'Région : IDF, NORD, EST, OUEST, SUD_EST, SUD_OUEST. Porte la sécurité ligne.',
    size_class STRING COMMENT 'Format : S (< 5 000 m²), M, L (> 9 000 m²).',
    surface_m2 INT COMMENT 'Surface de vente en m².',
    opened_on DATE COMMENT 'Date d''ouverture.',
    CONSTRAINT store_pk PRIMARY KEY (store_id)
)
COMMENT 'Dimension Magasins du data product Ventes et Stocks. RLS par région.'
WITH ROW FILTER ${catalog}.ops.rf_region ON (region)
AS SELECT
    store_id,
    store_name,
    city,
    region,
    size_class,
    surface_m2,
    opened_on
FROM ${catalog}.silver.stores;
