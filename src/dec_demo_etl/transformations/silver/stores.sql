-- Silver: store master data, typed, deduplicated (latest export wins) and checked.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.silver.stores (
    CONSTRAINT store_id_present EXPECT (store_id IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT region_known EXPECT (region IN ('IDF', 'NORD', 'EST', 'OUEST', 'SUD_EST', 'SUD_OUEST')),
    CONSTRAINT size_class_known EXPECT (size_class IN ('S', 'M', 'L'))
)
COMMENT 'Magasins nettoyés et dédoublonnés (dernier export reçu).'
AS SELECT
    store_id,
    store_name,
    city,
    region,
    size_class,
    surface_m2,
    opened_on
FROM ${catalog}.bronze.stores
QUALIFY row_number() OVER (PARTITION BY store_id ORDER BY _ingested_at DESC) = 1;
