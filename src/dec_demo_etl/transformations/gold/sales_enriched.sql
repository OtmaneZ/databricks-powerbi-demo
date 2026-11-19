-- Pipeline-private view shared by gold.fct_sales and ops.quarantine_sales:
-- sales lines enriched with the store region and the catalog price valid at the time
-- of sale (point-in-time join on the SCD2 product history).
-- is_latest_version implements "the latest delivery wins": when a source re-sends a
-- ticket line (correction file), only the most recently ingested version reaches gold.

CREATE TEMPORARY VIEW sales_enriched AS
SELECT
    s.ticket_id,
    s.line_no,
    s.sold_at,
    s.store_id,
    st.region,
    s.product_id,
    nullif(s.customer_id, '') AS customer_id,
    s.quantity,
    s.unit_price,
    s.discount_rate,
    s.payment_method,
    s.channel,
    s._source_file,
    s._ingested_at,
    p.product_id IS NOT NULL AS product_known,
    p.list_price AS list_price_at_sale,
    p.unit_cost AS unit_cost_at_sale,
    row_number() OVER (
        PARTITION BY s.ticket_id, s.line_no ORDER BY s._ingested_at DESC, s._source_file DESC
    ) = 1 AS is_latest_version
FROM ${catalog}.silver.sales AS s
LEFT JOIN ${catalog}.silver.stores AS st
    ON s.store_id = st.store_id
LEFT JOIN ${catalog}.silver.products_history AS p
    ON
        s.product_id = p.product_id
        AND s.sold_at >= p.__START_AT
        AND (p.__END_AT IS NULL OR s.sold_at < p.__END_AT);
