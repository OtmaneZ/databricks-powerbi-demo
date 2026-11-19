-- Security objects: entitlement table, row filter and column masks.
-- Must exist before the pipeline runs (the pipeline attaches them to its tables).
-- Idempotent. ${catalog} is substituted by dec_demo.governance.
--
-- Group membership is tested with is_account_group_member() OR is_member():
--   - target platform: account groups synced from the identity provider (SCIM);
--   - Free Edition: workspace-local groups only (no account console).

CREATE TABLE IF NOT EXISTS ${catalog}.ops.security_region_access (
    principal_group STRING NOT NULL COMMENT 'Groupe habilité (groupe de compte en cible, groupe local en Free Edition).',
    region STRING NOT NULL COMMENT 'Code région autorisé, ou * pour toutes les régions.',
    reason STRING COMMENT 'Justification métier de l''habilitation.',
    granted_on DATE COMMENT 'Date d''attribution.'
)
COMMENT 'Habilitations régionales : source unique de la RLS Unity Catalog (row filter) et de la RLS Power BI.';

MERGE INTO ${catalog}.ops.security_region_access AS t
USING (
    SELECT *
    FROM
        VALUES
        ('dec_platform_admins', '*', 'Équipe plateforme data : administration et support N2', DATE '2026-11-19'),
        ('dec_analysts_national', '*', 'Contrôle de gestion national', DATE '2026-11-19'),
        ('dec_region_idf', 'IDF', 'Direction régionale Île-de-France', DATE '2026-11-19'),
        ('dec_region_nord', 'NORD', 'Direction régionale Nord', DATE '2026-11-19'),
        ('dec_region_est', 'EST', 'Direction régionale Est', DATE '2026-11-19'),
        ('dec_region_ouest', 'OUEST', 'Direction régionale Ouest', DATE '2026-11-19'),
        ('dec_region_sud_est', 'SUD_EST', 'Direction régionale Sud-Est', DATE '2026-11-19'),
        ('dec_region_sud_ouest', 'SUD_OUEST', 'Direction régionale Sud-Ouest', DATE '2026-11-19')
            AS s (principal_group, region, reason, granted_on)
) AS s
    ON t.principal_group = s.principal_group AND t.region = s.region
WHEN NOT MATCHED THEN INSERT *;

-- Row filter. The parameter is named row_region on purpose: a parameter named "region"
-- would be shadowed by the column a.region inside the subquery and the filter would
-- return TRUE for every row (data leak).
CREATE OR REPLACE FUNCTION ${catalog}.ops.rf_region (row_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter : une ligne est visible si l''utilisateur appartient à un groupe habilité pour sa région (ou *).'
RETURN EXISTS (
    SELECT 1
    FROM ${catalog}.ops.security_region_access AS a
    WHERE
        a.region IN (row_region, '*')  -- noqa: RF03
        AND (is_account_group_member(a.principal_group) OR is_member(a.principal_group))
);

CREATE OR REPLACE FUNCTION ${catalog}.ops.mask_email (email STRING)
RETURNS STRING
COMMENT 'Masque l''email (partie avant @) sauf pour le groupe dec_pii_readers.'
RETURN
CASE
    WHEN is_account_group_member('dec_pii_readers') OR is_member('dec_pii_readers') THEN email
    ELSE regexp_replace(email, '^[^@]+', '***')
END;

CREATE OR REPLACE FUNCTION ${catalog}.ops.mask_phone (phone STRING)
RETURNS STRING
COMMENT 'Masque le téléphone (2 derniers chiffres visibles) sauf pour le groupe dec_pii_readers.'
RETURN
CASE
    WHEN is_account_group_member('dec_pii_readers') OR is_member('dec_pii_readers') THEN phone
    WHEN phone IS NULL THEN NULL
    ELSE concat('+33 * ** ** ** ', right(phone, 2))
END;

CREATE OR REPLACE FUNCTION ${catalog}.ops.mask_last_name (last_name STRING)
RETURNS STRING
COMMENT 'Masque le nom (initiale visible) sauf pour le groupe dec_pii_readers.'
RETURN
CASE
    WHEN is_account_group_member('dec_pii_readers') OR is_member('dec_pii_readers') THEN last_name
    WHEN last_name IS NULL THEN NULL
    ELSE concat(left(last_name, 1), '***')
END;
