-- Silver: product catalog with full price history (SCD type 2) built with AUTO CDC.
-- Two change feeds are merged into one private event stream:
--   1. the initial catalog load (all attributes),
--   2. dated price changes (price only; other attributes NULL and ignored).

CREATE OR REFRESH PRIVATE STREAMING TABLE product_events (
    product_id STRING,
    product_name STRING,
    family STRING,
    sub_family STRING,
    brand STRING,
    list_price DOUBLE,
    unit_cost DOUBLE,
    change_reason STRING,
    event_ts TIMESTAMP
);

CREATE FLOW product_events_initial_load
AS INSERT INTO product_events BY NAME
SELECT
    product_id,
    product_name,
    family,
    sub_family,
    brand,
    list_price,
    unit_cost,
    'Chargement initial du catalogue' AS change_reason,
    created_at AS event_ts
FROM STREAM (${catalog}.bronze.products);

CREATE FLOW product_events_price_changes
AS INSERT INTO product_events BY NAME
SELECT
    product_id,
    cast(NULL AS STRING) AS product_name,
    cast(NULL AS STRING) AS family,
    cast(NULL AS STRING) AS sub_family,
    cast(NULL AS STRING) AS brand,
    new_price AS list_price,
    cast(NULL AS DOUBLE) AS unit_cost,
    change_reason,
    effective_from AS event_ts
FROM STREAM (${catalog}.bronze.product_price_changes);

CREATE OR REFRESH STREAMING TABLE ${catalog}.silver.products_history
COMMENT 'Historique des produits (SCD2) : une ligne par version, bornée par __START_AT et __END_AT (NULL = version courante).';

CREATE FLOW products_history_cdc
AS AUTO CDC INTO ${catalog}.silver.products_history
FROM STREAM (product_events)
KEYS (product_id)
IGNORE NULL UPDATES
SEQUENCE BY event_ts
STORED AS SCD TYPE 2;
