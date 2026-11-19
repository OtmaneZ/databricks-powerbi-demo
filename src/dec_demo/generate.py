"""Synthetic data generator for the DEC demo (fictitious DIY retailer).

Writes raw "source system" exports to a Unity Catalog volume:

    /Volumes/<catalog>/bronze/landing/
        stores/                 CSV  (ERP export)
        products/               CSV  (ERP export)
        product_price_changes/  CSV  (ERP price updates, consumed with AUTO CDC)
        customers/              CSV  (loyalty CRM, fictitious personal data)
        sales/file_month=YYYY-MM/  JSON (POS export, one folder per month)
        stock_snapshots/        Parquet (warehouse weekly snapshots)

All randomness is derived from xxhash64 of stable keys, so a run is fully reproducible
and DataFrames can be recomputed safely (no cache/persist on serverless).

Usage (local, Databricks Connect on serverless):
    DATABRICKS_CONFIG_PROFILE=dec-demo uv run python -m dec_demo.generate --catalog dec_dev --sales-until 2026-09
    DATABRICKS_CONFIG_PROFILE=dec-demo uv run python -m dec_demo.generate --catalog dec_dev --only-month 2026-10
"""

from __future__ import annotations

import argparse
import math
import os
from collections.abc import Sequence

from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from dec_demo import reference_data as ref

N_PRODUCTS = 3_000
N_CUSTOMERS = 60_000
N_TICKETS = 600_000
STOCK_TOP_SKUS = 500
STOCK_WEEKS = 52

ACCENTS_FROM = "éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ"
ACCENTS_TO = "eeeeaaaiioouuucEEEEAAAIIOOUUUC"
HOLIDAYS = ["2024-12-25", "2025-01-01", "2025-05-01", "2025-12-25", "2026-01-01", "2026-05-01"]

# Spark dayofweek: 1 = Sunday ... 7 = Saturday
WEEKDAY_FACTOR = {1: 0.35, 2: 0.90, 3: 0.85, 4: 1.00, 5: 0.90, 6: 1.10, 7: 1.60}
MONTH_FACTOR = {
    1: 0.75,
    2: 0.80,
    3: 1.00,
    4: 1.25,
    5: 1.30,
    6: 1.15,
    7: 1.00,
    8: 0.85,
    9: 1.00,
    10: 1.00,
    11: 0.95,
    12: 1.10,
}
GARDEN_MONTH_FACTOR = {
    1: 0.30,
    2: 0.40,
    3: 0.80,
    4: 1.00,
    5: 1.00,
    6: 0.90,
    7: 0.70,
    8: 0.50,
    9: 0.50,
    10: 0.40,
    11: 0.25,
    12: 0.20,
}
STORE_SIZE_FACTOR = {"L": 1.6, "M": 1.0, "S": 0.6}


# --------------------------------------------------------------------------- helpers
def get_spark() -> SparkSession:
    """Active session on Databricks compute, Databricks Connect (serverless) locally."""
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    if os.environ.get("DATABRICKS_RUNTIME_VERSION"):  # job task on Databricks compute
        return SparkSession.builder.getOrCreate()
    from databricks.connect import DatabricksSession

    return DatabricksSession.builder.serverless(True).getOrCreate()


def u(salt: str, *cols: Column | str) -> Column:
    """Deterministic pseudo-uniform value in [0, 1) derived from stable keys."""
    prime = 1_000_000_007
    return F.pmod(F.xxhash64(F.lit(salt), *cols), F.lit(prime)).cast("double") / F.lit(float(prime))


def normal(salt: str, *cols: Column | str) -> Column:
    """Deterministic standard normal value (Box-Muller)."""
    u1 = F.greatest(u(f"{salt}_a", *cols), F.lit(1e-12))
    u2 = u(f"{salt}_b", *cols)
    return F.sqrt(F.lit(-2.0) * F.log(u1)) * F.cos(F.lit(2 * math.pi) * u2)


def pick(uniform: Column, values: Sequence[str], weights: Sequence[float]) -> Column:
    """Weighted categorical choice from a uniform column."""
    total = float(sum(weights))
    expr = None
    cumulative = 0.0
    for value, weight in zip(values[:-1], weights[:-1], strict=True):
        cumulative += weight / total
        expr = F.when(uniform < cumulative, F.lit(value)) if expr is None else expr.when(uniform < cumulative, value)
    return expr.otherwise(F.lit(values[-1])) if expr is not None else F.lit(values[-1])


def lookup(mapping: dict, key: Column) -> Column:
    return F.create_map(*[F.lit(x) for kv in mapping.items() for x in kv])[key]


def build_slots(df: DataFrame, key_col: str, weight_col: str, total_slots: int | None) -> tuple[DataFrame, int]:
    """Explode rows into contiguous integer slots proportional to their weight.

    A child row picks a parent with `pmod(hash, n_slots)` then an equi-join on `slot`,
    which gives weighted sampling without driver-side loops.
    """
    total_w = df.agg(F.sum(weight_col)).first()[0]
    scale = 1.0 if total_slots is None else total_slots / total_w
    n = F.greatest(F.lit(1), F.round(F.col(weight_col) * F.lit(scale)).cast("long"))
    sized = df.withColumn("_n", n)
    w = Window.orderBy(key_col).rowsBetween(Window.unboundedPreceding, Window.currentRow)
    sized = sized.withColumn("_end", F.sum("_n").over(w)).withColumn("_start", F.col("_end") - F.col("_n"))
    n_slots = int(sized.agg(F.sum("_n")).first()[0])
    slots = (
        sized.withColumn("_k", F.explode(F.sequence(F.lit(0).cast("long"), F.col("_n") - 1)))
        .withColumn("slot", F.col("_start") + F.col("_k"))
        .drop("_n", "_end", "_start", "_k")
    )
    return slots, n_slots


# --------------------------------------------------------------------------- master data
def gen_stores(spark: SparkSession) -> DataFrame:
    rows = []
    for region, cities in ref.STORES_BY_REGION.items():
        for city in cities:
            rows.append((f"S{len(rows) + 1:03d}", f"Magasin {city}", city, region))
    schema = "store_id STRING, store_name STRING, city STRING, region STRING"
    df = spark.createDataFrame(rows, schema)
    size = pick(u("store_size", "store_id"), ["L", "M", "S"], [0.25, 0.50, 0.25])
    return (
        df.withColumn("size_class", size)
        .withColumn(
            "surface_m2",
            F.when(F.col("size_class") == "L", 9000).when(F.col("size_class") == "M", 6000).otherwise(3500)
            + F.floor(u("store_surface", "store_id") * 1500).cast("int"),
        )
        .withColumn(
            "opened_on",
            F.date_add(F.lit("1995-01-01").cast("date"), F.floor(u("store_open", "store_id") * 10000).cast("int")),
        )
    )


def gen_products(spark: SparkSession) -> DataFrame:
    fam_rows, lo = [], 0.0
    for name, (share, median, sigma, margin, qty_mult, subs) in ref.FAMILIES.items():
        fam_rows.append((name, lo, lo + share, math.log(median), sigma, margin, qty_mult, subs))
        lo += share
    fam_schema = (
        "family STRING, lo DOUBLE, hi DOUBLE, log_median DOUBLE, sigma DOUBLE, margin_rate DOUBLE, "
        "qty_mult DOUBLE, sub_families ARRAY<STRING>"
    )
    families = spark.createDataFrame(fam_rows, fam_schema)

    base = spark.range(N_PRODUCTS, numPartitions=8).withColumn("u_fam", u("prod_family", "id") * F.lit(lo))
    df = base.join(F.broadcast(families), (F.col("u_fam") >= F.col("lo")) & (F.col("u_fam") < F.col("hi")))

    brands = F.array(*[F.lit(b) for b in ref.BRANDS])
    qualifiers = F.array(*[F.lit(q) for q in ref.PRODUCT_QUALIFIERS])
    sub_family = F.element_at(
        "sub_families", (F.pmod(F.xxhash64(F.lit("sub"), "id"), F.size("sub_families")) + 1).cast("int")
    )
    list_price = F.round(
        F.greatest(F.lit(0.99), F.exp(F.col("log_median") + F.col("sigma") * normal("price", "id"))), 2
    )
    pareto = F.least(F.lit(300.0), F.pow(F.lit(1.0) - u("popularity", "id"), F.lit(-1 / 1.16)))

    df = (
        df.select(
            F.format_string("P%05d", F.col("id") + 1).alias("product_id"),
            "family",
            sub_family.alias("sub_family"),
            F.element_at(
                brands, (F.pmod(F.xxhash64(F.lit("brand"), "id"), F.lit(len(ref.BRANDS))) + 1).cast("int")
            ).alias("brand"),
            F.element_at(
                qualifiers,
                (F.pmod(F.xxhash64(F.lit("qual"), "id"), F.lit(len(ref.PRODUCT_QUALIFIERS))) + 1).cast("int"),
            ).alias("qualifier"),
            list_price.alias("list_price"),
            "margin_rate",
            "qty_mult",
            pareto.alias("popularity"),
        )
        .withColumn(
            "product_name",
            F.concat_ws(" ", "sub_family", "qualifier", "brand", F.concat(F.lit("#"), F.substring("product_id", 3, 4))),
        )
        .withColumn(
            "unit_cost",
            F.round(
                F.col("list_price") * (F.lit(1.0) - F.col("margin_rate") + (u("cost", "product_id") - 0.5) * 0.10), 2
            ),
        )
        .withColumn("created_at", F.lit(f"{ref.HISTORY_START} 00:00:00").cast("timestamp"))
    )
    # Stockout scope: top garden SKUs by popularity.
    rank_w = Window.partitionBy("family").orderBy(F.col("popularity").desc(), "product_id")
    is_stockout = (F.col("family") == ref.STOCKOUT_FAMILY) & (F.row_number().over(rank_w) <= ref.STOCKOUT_TOP_SKUS)
    return df.withColumn("is_stockout_sku", is_stockout).drop("qualifier")


def gen_price_changes(products: DataFrame) -> DataFrame:
    span = F.datediff(F.lit("2026-09-30").cast("date"), F.lit("2025-01-15").cast("date"))
    up = u("pc_dir", "product_id") < 0.85
    factor = F.when(up, 1.03 + 0.09 * u("pc_up", "product_id")).otherwise(0.85 + 0.10 * u("pc_down", "product_id"))
    reason = F.when(
        up, pick(u("pc_reason", "product_id"), ["Hausse fournisseur", "Révision tarifaire annuelle"], [0.6, 0.4])
    ).otherwise(F.lit("Alignement concurrence"))
    return products.where(u("pc_select", "product_id") < 0.10).select(
        "product_id",
        F.round(F.col("list_price") * factor, 2).alias("new_price"),
        F.to_timestamp(
            F.date_add(F.lit("2025-01-15").cast("date"), F.floor(u("pc_date", "product_id") * span).cast("int"))
        ).alias("effective_from"),
        reason.alias("change_reason"),
    )


def gen_customers(spark: SparkSession, store_slots: DataFrame, n_store_slots: int) -> DataFrame:
    first = F.array(*[F.lit(x) for x in ref.FIRST_NAMES])
    last = F.array(*[F.lit(x) for x in ref.LAST_NAMES])
    df = spark.range(N_CUSTOMERS, numPartitions=8).select(
        F.format_string("C%06d", F.col("id") + 1).alias("customer_id"),
        F.element_at(first, (F.pmod(F.xxhash64(F.lit("fn"), "id"), F.lit(len(ref.FIRST_NAMES))) + 1).cast("int")).alias(
            "first_name"
        ),
        F.element_at(last, (F.pmod(F.xxhash64(F.lit("ln"), "id"), F.lit(len(ref.LAST_NAMES))) + 1).cast("int")).alias(
            "last_name"
        ),
        F.pmod(F.xxhash64(F.lit("home"), "id"), F.lit(n_store_slots)).alias("slot"),
        "id",
    )
    plain = lambda c: F.lower(F.regexp_replace(F.translate(F.col(c), ACCENTS_FROM, ACCENTS_TO), "[^A-Za-z]", ""))  # noqa: E731
    suffix = F.when(
        u("mail_num", "id") < 0.6, F.pmod(F.xxhash64(F.lit("mail_n"), "id"), F.lit(100)).cast("string")
    ).otherwise(F.lit(""))
    phone = F.when(
        u("phone", "id") < 0.6,
        F.concat(
            F.lit("+33 6 39 98 "),
            F.lpad(F.pmod(F.xxhash64(F.lit("ph1"), "id"), F.lit(100)).cast("string"), 2, "0"),
            F.lit(" "),
            F.lpad(F.pmod(F.xxhash64(F.lit("ph2"), "id"), F.lit(100)).cast("string"), 2, "0"),
        ),
    )
    return (
        df.join(store_slots.select("slot", F.col("store_id").alias("home_store_id")), "slot")
        .withColumn(
            "email", F.concat(plain("first_name"), F.lit("."), plain("last_name"), suffix, F.lit("@example.com"))
        )
        .withColumn("phone", phone)
        .withColumn("segment", F.when(u("segment", "id") < 0.25, F.lit("PRO")).otherwise(F.lit("PARTICULIER")))
        .withColumn(
            "loyalty_since",
            F.date_add(F.lit("2015-01-01").cast("date"), F.floor(u("loyalty", "id") * 4290).cast("int")),
        )
        .withColumn("marketing_optin", u("optin", "id") < 0.62)
        .drop("slot", "id")
    )


# --------------------------------------------------------------------------- transactions
def gen_calendar(spark: SparkSession) -> DataFrame:
    days = spark.sql(
        f"SELECT explode(sequence(DATE'{ref.HISTORY_START}', DATE'{ref.HISTORY_END}', INTERVAL 1 DAY)) AS sale_date"
    )
    trend = F.lit(1.0) + F.lit(0.05) * F.datediff("sale_date", F.lit(ref.HISTORY_START).cast("date")) / F.lit(365.0)
    weight = lookup(WEEKDAY_FACTOR, F.dayofweek("sale_date")) * lookup(MONTH_FACTOR, F.month("sale_date")) * trend
    weight = F.when(F.col("sale_date").cast("string").isin(HOLIDAYS), F.lit(0.0)).otherwise(weight)
    return days.withColumn("weight", weight).where("weight > 0")


def gen_sales(
    spark: SparkSession,
    stores: DataFrame,
    products: DataFrame,
    price_changes: DataFrame,
    customers: DataFrame,
    apply_price_incident: bool = True,
    only_price_incident_rows: bool = False,
) -> DataFrame:
    """Sales lines. With apply_price_incident=False and only_price_incident_rows=True it
    returns the corrected re-delivery of the incident lines (prices back in euros)."""
    day_slots, n_day = build_slots(gen_calendar(spark), "sale_date", "weight", 100_000)
    store_w = stores.withColumn("weight", lookup(STORE_SIZE_FACTOR, F.col("size_class")))
    store_slots, n_store = build_slots(store_w, "store_id", "weight", 4_000)
    cust_w = customers.withColumn("weight", F.when(F.col("segment") == "PRO", 4).otherwise(1))
    cust_slots, n_cust = build_slots(cust_w, "customer_id", "weight", None)
    prod_slots, n_prod = build_slots(products, "product_id", "popularity", 200_000)

    tickets = spark.range(N_TICKETS, numPartitions=64).select(
        F.format_string("T%08d", F.col("id") + 1).alias("ticket_id"),
        (u("identified", "id") < 0.45).alias("identified"),
        F.pmod(F.xxhash64(F.lit("day"), "id"), F.lit(n_day)).alias("day_slot"),
        F.pmod(F.xxhash64(F.lit("store"), "id"), F.lit(n_store)).alias("store_slot"),
        F.pmod(F.xxhash64(F.lit("cust"), "id"), F.lit(n_cust)).alias("cust_slot"),
        u("loyal_store", "id").alias("u_loyal"),
        u("hour", "id").alias("u_hour"),
        F.floor(u("minute", "id") * 60).cast("int").alias("minute"),
        F.floor(u("second", "id") * 60).cast("int").alias("second"),
        u("pay", "id").alias("u_pay"),
        u("channel", "id").alias("u_channel"),
        u("nlines", "id").alias("u_lines"),
    )
    tickets = (
        tickets.join(F.broadcast(day_slots.select(F.col("slot").alias("day_slot"), "sale_date")), "day_slot")
        .join(
            F.broadcast(
                store_slots.select(F.col("slot").alias("store_slot"), F.col("store_id").alias("random_store_id"))
            ),
            "store_slot",
        )
        .join(
            cust_slots.select(F.col("slot").alias("cust_slot"), "customer_id", "segment", "home_store_id"),
            "cust_slot",
        )
    )
    segment = F.when(F.col("identified"), F.col("segment")).otherwise(F.lit("PARTICULIER"))
    hours = [str(h) for h in range(8, 20)]
    hour_w = [4, 8, 11, 12, 8, 7, 10, 11, 11, 10, 6, 2]
    tickets = tickets.select(
        "ticket_id",
        F.when(F.col("identified") & (F.col("u_loyal") < 0.9), F.col("home_store_id"))
        .otherwise(F.col("random_store_id"))
        .alias("store_id"),
        F.when(F.col("identified"), F.col("customer_id")).alias("customer_id"),
        segment.alias("segment"),
        F.expr("make_timestamp(year(sale_date), month(sale_date), day(sale_date), 0, 0, 0)").alias("day_ts"),
        pick(F.col("u_hour"), hours, hour_w).cast("int").alias("hour"),
        "minute",
        "second",
        F.when(segment == "PRO", pick(F.col("u_pay"), ["COMPTE_PRO", "CB"], [0.6, 0.4]))
        .otherwise(pick(F.col("u_pay"), ["CB", "ESPECES", "CHEQUE"], [0.85, 0.10, 0.05]))
        .alias("payment_method"),
        pick(F.col("u_channel"), ["MAGASIN", "RETRAIT_DRIVE"], [0.92, 0.08]).alias("channel"),
        # 1 + floor(Exp(lambda)) lines: mean ~2.2 for consumers, ~3.5 for pros
        F.least(
            F.lit(15),
            F.lit(1)
            + F.floor(
                -F.log(F.greatest(F.col("u_lines"), F.lit(1e-12)))
                / F.when(segment == "PRO", F.lit(0.336)).otherwise(F.lit(0.606))
            ).cast("int"),
        ).alias("n_lines"),
    ).withColumn(
        "sold_at",
        F.col("day_ts") + F.make_interval(hours=F.col("hour"), mins=F.col("minute"), secs=F.col("second")),
    )

    lines = tickets.withColumn("line_no", F.explode(F.sequence(F.lit(1), F.col("n_lines")))).withColumn(
        "prod_slot", F.pmod(F.xxhash64(F.lit("prod"), "ticket_id", "line_no"), F.lit(n_prod))
    )
    lines = (
        lines.join(
            F.broadcast(
                prod_slots.select(
                    F.col("slot").alias("prod_slot"),
                    "product_id",
                    "family",
                    "list_price",
                    "qty_mult",
                    "is_stockout_sku",
                )
            ),
            "prod_slot",
        )
        .join(F.broadcast(price_changes.select("product_id", "new_price", "effective_from")), "product_id", "left")
        .join(F.broadcast(stores.select("store_id", "region", "city")), "store_id", "left")
    )

    k = ["ticket_id", "line_no"]
    month = F.month("sold_at")
    in_stockout = (
        (F.col("region") == ref.STOCKOUT_REGION)
        & F.col("is_stockout_sku")
        & F.col("sold_at").between(
            F.lit(ref.STOCKOUT_START).cast("timestamp"), F.lit(f"{ref.STOCKOUT_END} 23:59:59").cast("timestamp")
        )
    )
    keep = F.when(F.col("family") == "Jardin", u("garden_season", *k) < lookup(GARDEN_MONTH_FACTOR, month)).otherwise(
        F.lit(True)
    ) & ~(in_stockout & (u("stockout_keep", *k) >= 0.02))
    lam_q = F.when(F.col("segment") == "PRO", F.lit(0.5)).otherwise(F.lit(1.2))
    base_qty = F.lit(1) + F.floor(-F.log(F.greatest(u("qty", *k), F.lit(1e-12))) / lam_q)
    unit_price = F.when(F.col("sold_at") >= F.col("effective_from"), F.col("new_price")).otherwise(F.col("list_price"))
    discount = F.when(F.col("segment") == "PRO", F.round(0.05 + 0.10 * u("disc_pro", *k), 2)).otherwise(
        F.when(u("promo", *k) < 0.08, F.lit(0.10)).otherwise(F.lit(0.0))
    )

    sales = lines.where(keep).select(
        "ticket_id",
        "line_no",
        "store_id",
        "product_id",
        "customer_id",
        "sold_at",
        F.greatest(F.lit(1), F.round(base_qty * F.col("qty_mult"))).cast("int").alias("quantity"),
        unit_price.alias("unit_price"),
        discount.alias("discount_rate"),
        "payment_method",
        "channel",
        "city",
    )

    # ---- deliberate data defects (caught later by pipeline expectations)
    incident = (F.col("city") == ref.PRICE_INCIDENT_CITY) & (
        F.to_date("sold_at") == F.lit(ref.PRICE_INCIDENT_DATE).cast("date")
    )
    if only_price_incident_rows:
        sales = sales.where(incident)
    if not apply_price_incident:
        incident = F.lit(False)
    sales = (
        sales.withColumn(
            "product_id",
            F.when(
                u("bad_product", *k) < 0.003,
                F.format_string("P9%04d", F.pmod(F.xxhash64(F.lit("bad_pid"), *k), F.lit(10000)).cast("int")),
            ).otherwise(F.col("product_id")),
        )
        .withColumn(
            "store_id", F.when(u("null_store", *k) < 0.0005, F.lit(None).cast("string")).otherwise(F.col("store_id"))
        )
        .withColumn("quantity", F.when(u("zero_qty", *k) < 0.001, F.lit(0)).otherwise(F.col("quantity")))
        .withColumn(
            "unit_price", F.round(F.when(incident, F.col("unit_price") * 100).otherwise(F.col("unit_price")), 2)
        )
        .withColumn("file_month", F.date_format("sold_at", "yyyy-MM"))
        .withColumn("sold_at", F.date_format("sold_at", "yyyy-MM-dd'T'HH:mm:ss"))
        .drop("city")
    )
    return sales


def gen_stock(spark: SparkSession, stores: DataFrame, products: DataFrame) -> DataFrame:
    top = products.withColumn(
        "_r", F.row_number().over(Window.orderBy(F.col("popularity").desc(), "product_id"))
    ).where(F.col("_r") <= STOCK_TOP_SKUS)
    weeks = spark.sql(
        f"SELECT explode(sequence(date_sub(next_day(DATE'{ref.HISTORY_END}', 'MON'), 7 * {STOCK_WEEKS}), "
        f"date_sub(next_day(DATE'{ref.HISTORY_END}', 'MON'), 7), INTERVAL 7 DAY)) AS snapshot_date"
    )
    grid = weeks.crossJoin(F.broadcast(stores.select("store_id", "region", "size_class"))).crossJoin(
        F.broadcast(top.select("product_id", "family", "popularity", "is_stockout_sku"))
    )
    k = ["snapshot_date", "store_id", "product_id"]
    season = F.when(F.col("family") == "Jardin", lookup(GARDEN_MONTH_FACTOR, F.month("snapshot_date"))).otherwise(
        F.lit(1.0)
    )
    weekly_demand = F.greatest(
        F.lit(1.0), F.col("popularity") * lookup(STORE_SIZE_FACTOR, F.col("size_class")) * 0.4 * season
    )
    stockout = (
        (F.col("region") == ref.STOCKOUT_REGION)
        & F.col("is_stockout_sku")
        & F.col("snapshot_date").between(F.lit(ref.STOCKOUT_START).cast("date"), F.lit(ref.STOCKOUT_END).cast("date"))
    )
    stock = F.when(stockout | (u("random_oos", *k) < 0.02), F.lit(0)).otherwise(
        F.round(weekly_demand * (1.5 + 3.0 * u("cover", *k))).cast("int")
    )
    return grid.select(
        "snapshot_date",
        "store_id",
        "product_id",
        stock.alias("stock_qty"),
        F.round(weekly_demand * 1.5).cast("int").alias("reorder_point"),
    )


# --------------------------------------------------------------------------- writers
def write_csv(df: DataFrame, path: str) -> None:
    df.coalesce(1).write.mode("overwrite").option("header", True).option("sep", ";").option("encoding", "UTF-8").csv(
        path
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate fictitious retail source exports into a UC volume.")
    parser.add_argument("--catalog", required=True)
    parser.add_argument(
        "--sales-until", default=ref.HISTORY_END[:7], help="Last sales month to write (YYYY-MM), full load"
    )
    parser.add_argument(
        "--only-month", default=None, help="Write only this sales month folder (YYYY-MM), e.g. live drop"
    )
    parser.add_argument(
        "--correct-incident",
        action="store_true",
        help="Append the source's corrected re-delivery of the price incident lines (runbook resolution)",
    )
    args = parser.parse_args(argv)

    spark = get_spark()
    catalog = args.catalog
    landing = f"/Volumes/{catalog}/bronze/landing"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.bronze COMMENT 'Raw ingested data, as received from sources'")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze.landing COMMENT 'Landing zone for source system exports'")

    stores = gen_stores(spark)
    products = gen_products(spark)
    price_changes = gen_price_changes(products)
    store_w = stores.withColumn("weight", lookup(STORE_SIZE_FACTOR, F.col("size_class")))
    store_slots, n_store = build_slots(store_w, "store_id", "weight", 4_000)
    customers = gen_customers(spark, store_slots, n_store)
    sales = gen_sales(spark, stores, products, price_changes, customers)

    if args.correct_incident:
        month = ref.PRICE_INCIDENT_DATE[:7]
        fixed = gen_sales(
            spark, stores, products, price_changes, customers, apply_price_incident=False, only_price_incident_rows=True
        )
        fixed.drop("file_month").coalesce(1).write.mode("append").json(f"{landing}/sales/file_month={month}")
        print(f"Appended corrected incident lines ({ref.PRICE_INCIDENT_CITY}, {ref.PRICE_INCIDENT_DATE}) to {month}")
        return

    if args.only_month:
        month_df = sales.where(F.col("file_month") == args.only_month).drop("file_month")
        month_df.repartition(2).write.mode("overwrite").json(f"{landing}/sales/file_month={args.only_month}")
        print(f"Wrote sales month {args.only_month} to {landing}/sales/")
        return

    write_csv(stores, f"{landing}/stores")
    write_csv(
        products.select(
            "product_id", "product_name", "family", "sub_family", "brand", "list_price", "unit_cost", "created_at"
        ),
        f"{landing}/products",
    )
    write_csv(price_changes, f"{landing}/product_price_changes")
    write_csv(customers, f"{landing}/customers")
    (
        sales.where(F.col("file_month") <= args.sales_until)
        .repartition("file_month")
        .write.mode("overwrite")
        .partitionBy("file_month")
        .json(f"{landing}/sales")
    )
    gen_stock(spark, stores, products).repartition(4).write.mode("overwrite").parquet(f"{landing}/stock_snapshots")
    print(f"Wrote all source exports to {landing} (sales until {args.sales_until})")


if __name__ == "__main__":
    main()
