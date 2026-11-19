"""Export the gold data products (and the ops tables the report needs) to Parquet files
for the Power BI project, so that it opens on any Windows machine without Databricks
credentials.

    DATABRICKS_CONFIG_PROFILE=dec-demo uv run python -m dec_demo.export_gold --catalog dec_dev

Controls, all blocking:
- row count of each file = row count of the source table;
- each file stays under the GitHub limit (50 MB); otherwise it is not written;
- no personal data column in any file, and dim_customer limited to an allowlist;
- the exporting account sees every region (the row filter ops.rf_region also applies to
  exports: a restricted account would silently produce truncated files).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "powerbi" / "data"
MAX_BYTES = 50 * 1024 * 1024
EXPECTED_REGIONS = 6
EXPECTED_STORES = 40

# (schema.table, sort columns). The sort keeps files deterministic and compresses better.
EXPORTS: list[tuple[str, list[str]]] = [
    ("gold.fct_sales", ["sale_date", "store_id", "ticket_id", "line_no"]),
    ("gold.fct_stock_weekly", ["snapshot_date", "store_id", "product_id"]),
    ("gold.dim_store", ["store_id"]),
    ("gold.dim_product", ["product_id"]),
    ("gold.dim_customer", ["customer_id"]),
    ("gold.dim_date", ["calendar_date"]),
    # Entitlements: single source of the regional row-level security, reused by Power BI.
    ("ops.security_region_access", ["principal_group", "region"]),
    # Quality quarantine: needed by the report page on data quality and the price incident.
    ("ops.quarantine_sales", ["sold_at", "ticket_id", "line_no", "quarantine_reason"]),
]

PERSONAL_DATA_COLUMNS = {"first_name", "last_name", "email", "phone"}
DIM_CUSTOMER_ALLOWED = {"customer_id", "customer_segment", "home_store_id", "loyalty_since", "marketing_optin"}


def check_columns(table: str, columns: Sequence[str]) -> None:
    leaked = PERSONAL_DATA_COLUMNS.intersection(columns)
    if leaked:
        raise SystemExit(f"{table}: personal data columns {sorted(leaked)}: export refused")
    if table == "gold.dim_customer" and set(columns) != DIM_CUSTOMER_ALLOWED:
        raise SystemExit(f"gold.dim_customer: columns {sorted(columns)} differ from the allowlist")


def naive_timestamps(table: pa.Table) -> pa.Table:
    """Drop the time zone of timestamp columns (values are UTC wall-clock times).

    Power Query reads a zoned Parquet timestamp as datetimezone; the model uses datetime.
    """
    fields = []
    for field in table.schema:
        if pa.types.is_timestamp(field.type) and field.type.tz is not None:
            fields.append(pa.field(field.name, pa.timestamp("us"), field.nullable))
        else:
            fields.append(field)
    return table.cast(pa.schema(fields))


def write_parquet(table: pa.Table, target: Path) -> int:
    temporary = target.with_suffix(".parquet.tmp")
    pq.write_table(table, temporary, compression="snappy", use_dictionary=True, row_group_size=256_000)
    size = temporary.stat().st_size
    if size >= MAX_BYTES:
        temporary.unlink()
        raise SystemExit(
            f"{target.name}: {size / 1e6:.1f} MB, above the 50 MB GitHub limit. File not written: "
            "choose an aggregation or a consistent sample before exporting."
        )
    temporary.replace(target)
    return size


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export gold tables to powerbi/data/*.parquet")
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args(argv)

    from dec_demo.generate import get_spark

    spark = get_spark()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    regions = spark.sql(f"SELECT count(DISTINCT region) AS n FROM {args.catalog}.gold.dim_store").first()["n"]
    stores = spark.sql(f"SELECT count(*) AS n FROM {args.catalog}.gold.dim_store").first()["n"]
    if regions != EXPECTED_REGIONS or stores != EXPECTED_STORES:
        raise SystemExit(
            f"The exporting account sees {regions} regions and {stores} stores "
            f"(expected {EXPECTED_REGIONS} and {EXPECTED_STORES}): the row filter restricts it. "
            "Run the export with an account in dec_platform_admins."
        )

    manifest = {}
    for name, sort_columns in EXPORTS:
        full_name = f"{args.catalog}.{name}"
        df = spark.table(full_name)
        check_columns(name, df.columns)
        source_rows = df.count()
        table = naive_timestamps(df.orderBy(*sort_columns).toArrow())
        target = OUTPUT_DIR / f"{name.split('.')[1]}.parquet"
        size = write_parquet(table, target)
        file_rows = pq.ParquetFile(target).metadata.num_rows
        if file_rows != source_rows:
            raise SystemExit(f"{target.name}: {file_rows} rows in the file, {source_rows} in {full_name}")
        manifest[target.name] = {
            "source": name,
            "rows": file_rows,
            "bytes": size,
            "columns": {field.name: str(field.type) for field in table.schema},
        }
        print(f"{target.name:32} {file_rows:>10,} rows  {size / 1e6:6.2f} MB  (source {full_name}: {source_rows:,})")

    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"manifest.json written ({len(manifest)} files)")


if __name__ == "__main__":
    sys.exit(main())
