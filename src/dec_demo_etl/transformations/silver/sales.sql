-- Silver: POS sales lines, typed and checked. Structural defects are dropped here and
-- listed in ops.quarantine_sales for follow-up; price plausibility is checked in gold
-- against the catalog price valid at the time of sale.

CREATE OR REFRESH STREAMING TABLE ${catalog}.silver.sales (
    CONSTRAINT store_id_present EXPECT (store_id IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT quantity_positive EXPECT (quantity > 0) ON VIOLATION DROP ROW,
    CONSTRAINT sold_at_valid EXPECT (sold_at IS NOT NULL) ON VIOLATION DROP ROW,
    CONSTRAINT unit_price_positive EXPECT (unit_price > 0) ON VIOLATION DROP ROW,
    CONSTRAINT discount_in_range EXPECT (discount_rate BETWEEN 0 AND 0.5)
)
CLUSTER BY AUTO
COMMENT 'Lignes de ventes typées et contrôlées. Les lignes rejetées sont tracées dans ops.quarantine_sales.'
AS SELECT
    ticket_id,
    line_no,
    store_id,
    product_id,
    customer_id,
    to_timestamp(sold_at) AS sold_at,
    quantity,
    unit_price,
    discount_rate,
    payment_method,
    channel,
    _source_file,
    _ingested_at
FROM STREAM (${catalog}.bronze.sales);
