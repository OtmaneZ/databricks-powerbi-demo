-- Gold data product: sales fact at ticket-line grain.
-- Row-level security by region (ops.rf_region); price plausibility checked against the
-- catalog price valid at the time of sale; rejected lines go to ops.quarantine_sales.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.fct_sales (
    ticket_id STRING COMMENT 'Numéro de ticket de caisse.',
    line_no INT COMMENT 'Numéro de ligne dans le ticket.',
    sale_date DATE COMMENT 'Date de vente (clé vers gold.dim_date).',
    sold_at TIMESTAMP COMMENT 'Horodatage du passage en caisse.',
    store_id STRING COMMENT 'Magasin (clé vers gold.dim_store).',
    region STRING COMMENT 'Région du magasin. Porte la sécurité ligne (row filter ops.rf_region).',
    product_id STRING COMMENT 'Produit (clé vers gold.dim_product). UNKNOWN si la référence est absente du catalogue.',
    source_product_id STRING COMMENT 'Référence produit telle que reçue de la caisse (traçabilité).',
    customer_id STRING COMMENT 'Client (clé vers gold.dim_customer). ANONYMOUS pour une vente non identifiée.',
    customer_segment STRING COMMENT 'PRO ou PARTICULIER (PARTICULIER pour les ventes non identifiées).',
    quantity INT COMMENT 'Quantité vendue.',
    unit_price DECIMAL(12, 2) COMMENT 'Prix unitaire encaissé, avant remise.',
    list_price_at_sale DECIMAL(12, 2) COMMENT 'Prix catalogue en vigueur à la date de vente (historique SCD2).',
    discount_rate DECIMAL(4, 2) COMMENT 'Taux de remise appliqué (0 à 0,5).',
    net_amount DECIMAL(14, 2) COMMENT 'Chiffre d''affaires net : quantité × prix unitaire × (1 - remise).',
    cost_amount DECIMAL(14, 2) COMMENT 'Coût d''achat : quantité × coût unitaire en vigueur. NULL si produit inconnu.',
    gross_margin DECIMAL(14, 2) COMMENT 'Marge brute : CA net - coût d''achat. NULL si produit inconnu.',
    payment_method STRING COMMENT 'Moyen de paiement : CB, ESPECES, CHEQUE, COMPTE_PRO.',
    channel STRING COMMENT 'Canal : MAGASIN ou RETRAIT_DRIVE.',
    CONSTRAINT price_consistent_with_catalog
    EXPECT (list_price_at_sale IS NULL OR unit_price <= list_price_at_sale * 1.5) ON VIOLATION DROP ROW,
    CONSTRAINT product_in_catalog EXPECT (product_id <> 'UNKNOWN')
)
CLUSTER BY AUTO
COMMENT 'Data product Ventes : une ligne par ligne de ticket. Source certifiée du CA et de la marge. RLS par région.'
WITH ROW FILTER ${catalog}.ops.rf_region ON (region)
AS SELECT
    e.ticket_id,
    e.line_no,
    cast(e.sold_at AS DATE) AS sale_date,
    e.sold_at,
    e.store_id,
    e.region,
    CASE WHEN e.product_known THEN e.product_id ELSE 'UNKNOWN' END AS product_id,
    e.product_id AS source_product_id,
    coalesce(e.customer_id, 'ANONYMOUS') AS customer_id,
    coalesce(c.segment, 'PARTICULIER') AS customer_segment,
    e.quantity,
    cast(e.unit_price AS DECIMAL(12, 2)) AS unit_price,
    cast(e.list_price_at_sale AS DECIMAL(12, 2)) AS list_price_at_sale,
    cast(e.discount_rate AS DECIMAL(4, 2)) AS discount_rate,
    cast(e.quantity * e.unit_price * (1 - e.discount_rate) AS DECIMAL(14, 2)) AS net_amount,
    cast(e.quantity * e.unit_cost_at_sale AS DECIMAL(14, 2)) AS cost_amount,
    cast(e.quantity * e.unit_price * (1 - e.discount_rate) - e.quantity * e.unit_cost_at_sale AS DECIMAL(14, 2))
        AS gross_margin,
    e.payment_method,
    e.channel
FROM sales_enriched AS e
LEFT JOIN ${catalog}.silver.customers AS c
    ON e.customer_id = c.customer_id
WHERE e.is_latest_version;
