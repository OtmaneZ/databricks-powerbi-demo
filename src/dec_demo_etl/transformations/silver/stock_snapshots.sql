-- Silver: weekly stock snapshots, typed and checked.

CREATE OR REFRESH STREAMING TABLE ${catalog}.silver.stock_snapshots (
    CONSTRAINT keys_present EXPECT (snapshot_date IS NOT NULL AND store_id IS NOT NULL AND product_id IS NOT NULL)
    ON VIOLATION DROP ROW,
    CONSTRAINT stock_not_negative EXPECT (stock_qty >= 0)
)
CLUSTER BY AUTO
COMMENT 'Stocks hebdomadaires (lundi) par magasin et produit, contrôlés.'
AS SELECT
    snapshot_date,
    store_id,
    product_id,
    stock_qty,
    reorder_point
FROM STREAM (${catalog}.bronze.stock_snapshots);
