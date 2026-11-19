-- Access grants executable on Databricks Free Edition.
-- Free Edition has no account groups, so Unity Catalog grants can only target users or
-- the built-in `account users` group. Fine-grained access is still enforced by the row
-- filter (ops.rf_region) and the column masks, which test workspace-local groups.
-- Target state with group-based grants: sql/governance/target/30_grants_target.sql.

GRANT USE CATALOG ON CATALOG ${catalog} TO `account users`;  -- noqa: RF05
GRANT USE SCHEMA ON SCHEMA ${catalog}.gold TO `account users`;  -- noqa: RF05
GRANT SELECT ON SCHEMA ${catalog}.gold TO `account users`;  -- noqa: RF05
