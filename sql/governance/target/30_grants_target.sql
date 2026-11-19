-- TARGET STATE (not executable on Free Edition): role-based grants to account groups
-- provisioned by SCIM from the identity provider. Principle of least privilege:
-- consumers only see gold; bronze, silver and ops are reserved to the platform team.
--
-- Role                      Groups                         Access
-- Platform team             dec_platform_admins            all schemas, write
-- National analysts         dec_analysts_national          gold, read (all regions via rf_region)
-- Regional managers         dec_region_<region>            gold, read (own region via rf_region)
-- Personal data readers     dec_pii_readers                silver.customers unmasked (via masks)

GRANT USE CATALOG ON CATALOG ${catalog} TO `dec_platform_admins`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.bronze TO `dec_platform_admins`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.silver TO `dec_platform_admins`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.gold TO `dec_platform_admins`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.ops TO `dec_platform_admins`;
GRANT ALL PRIVILEGES ON SCHEMA ${catalog}.migration TO `dec_platform_admins`;

GRANT USE CATALOG ON CATALOG ${catalog} TO `dec_analysts_national`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.gold TO `dec_analysts_national`;
GRANT SELECT ON SCHEMA ${catalog}.gold TO `dec_analysts_national`;

GRANT USE CATALOG ON CATALOG ${catalog} TO `dec_region_nord`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.gold TO `dec_region_nord`;
GRANT SELECT ON SCHEMA ${catalog}.gold TO `dec_region_nord`;
-- Same three grants for dec_region_idf, dec_region_est, dec_region_ouest,
-- dec_region_sud_est and dec_region_sud_ouest.

GRANT USE CATALOG ON CATALOG ${catalog} TO `dec_pii_readers`;
GRANT USE SCHEMA ON SCHEMA ${catalog}.silver TO `dec_pii_readers`;
GRANT SELECT ON TABLE ${catalog}.silver.customers TO `dec_pii_readers`;

-- Entitlement table: only the platform team may change who sees which region.
GRANT MODIFY ON TABLE ${catalog}.ops.security_region_access TO `dec_platform_admins`;
