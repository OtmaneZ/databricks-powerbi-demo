-- Gold data product: weekly stock position per store and product, with stockout flags.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.fct_stock_weekly (
    snapshot_date DATE COMMENT 'Date de l''inventaire hebdomadaire (lundi). Clé vers gold.dim_date.',
    store_id STRING COMMENT 'Magasin (clé vers gold.dim_store).',
    region STRING COMMENT 'Région du magasin. Porte la sécurité ligne (row filter ops.rf_region).',
    product_id STRING COMMENT 'Produit (clé vers gold.dim_product).',
    stock_qty INT COMMENT 'Quantité en stock au moment de l''inventaire.',
    reorder_point INT COMMENT 'Seuil de réapprovisionnement.',
    is_out_of_stock BOOLEAN COMMENT 'Vrai si le stock est nul (rupture).',
    is_below_reorder_point BOOLEAN COMMENT 'Vrai si le stock est sous le seuil de réapprovisionnement.'
)
CLUSTER BY AUTO
COMMENT 'Data product Stocks : position hebdomadaire par magasin et produit (500 références principales). RLS par région.'
WITH ROW FILTER ${catalog}.ops.rf_region ON (region)
AS SELECT
    k.snapshot_date,
    k.store_id,
    st.region,
    k.product_id,
    k.stock_qty,
    k.reorder_point,
    k.stock_qty = 0 AS is_out_of_stock,
    k.stock_qty < k.reorder_point AS is_below_reorder_point
FROM ${catalog}.silver.stock_snapshots AS k
INNER JOIN ${catalog}.silver.stores AS st
    ON k.store_id = st.store_id;
