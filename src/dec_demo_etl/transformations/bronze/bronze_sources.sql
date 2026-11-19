-- Bronze: raw source exports ingested incrementally with Auto Loader (read_files).
-- One streaming table per source, kept as received plus lineage columns.
-- ${catalog} and ${landing_path} come from the pipeline configuration.

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.stores
COMMENT 'Magasins, export ERP brut (CSV).'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files(
    '${landing_path}/stores',
    format => 'csv', header => TRUE, sep => ';',
    schemaHints => 'store_id STRING, surface_m2 INT, opened_on DATE'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.products
COMMENT 'Référentiel produits, export ERP brut (CSV). Chargement initial du catalogue.'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files(
    '${landing_path}/products',
    format => 'csv', header => TRUE, sep => ';',
    schemaHints => 'product_id STRING, list_price DOUBLE, unit_cost DOUBLE, created_at TIMESTAMP'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.product_price_changes
COMMENT 'Changements de prix datés, export ERP brut (CSV). Alimente l''historique produits (AUTO CDC, SCD2).'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files(
    '${landing_path}/product_price_changes',
    format => 'csv', header => TRUE, sep => ';',
    schemaHints => 'product_id STRING, new_price DOUBLE, effective_from TIMESTAMP'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.customers
COMMENT 'Clients fidélité, export CRM brut (CSV). Contient des données personnelles fictives : accès restreint.'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files(
    '${landing_path}/customers',
    format => 'csv', header => TRUE, sep => ';',
    schemaHints => 'customer_id STRING, phone STRING, loyalty_since DATE, marketing_optin BOOLEAN'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.sales
CLUSTER BY AUTO
COMMENT 'Lignes de tickets de caisse, export brut (JSON, un dossier par mois). Aucun contrôle appliqué à ce stade.'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files(
    '${landing_path}/sales',
    format => 'json',
    schemaHints => 'line_no INT, sold_at STRING, quantity INT, unit_price DOUBLE, discount_rate DOUBLE'
);

CREATE OR REFRESH STREAMING TABLE ${catalog}.bronze.stock_snapshots
CLUSTER BY AUTO
COMMENT 'Stocks hebdomadaires par magasin et produit, export entrepôt brut (Parquet).'
AS SELECT
    *,
    _metadata.file_path AS _source_file,
    current_timestamp() AS _ingested_at
FROM STREAM read_files('${landing_path}/stock_snapshots', format => 'parquet');
