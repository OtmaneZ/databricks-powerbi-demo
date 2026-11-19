-- Gold dimension: calendar with French labels and public holidays.

CREATE OR REFRESH MATERIALIZED VIEW ${catalog}.gold.dim_date (
    calendar_date DATE NOT NULL COMMENT 'Date (clé primaire).',
    year INT COMMENT 'Année civile.',
    quarter INT COMMENT 'Trimestre (1 à 4).',
    month INT COMMENT 'Mois (1 à 12).',
    month_name STRING COMMENT 'Nom du mois en français.',
    year_month STRING COMMENT 'Année-mois au format AAAA-MM.',
    iso_week INT COMMENT 'Semaine ISO.',
    day_of_week INT COMMENT 'Jour de la semaine ISO : 1 = lundi … 7 = dimanche.',
    day_name STRING COMMENT 'Nom du jour en français.',
    is_weekend BOOLEAN COMMENT 'Vrai le samedi et le dimanche.',
    is_public_holiday BOOLEAN COMMENT 'Vrai les jours fériés en France métropolitaine.',
    CONSTRAINT date_pk PRIMARY KEY (calendar_date)
)
COMMENT 'Dimension Calendrier (novembre 2024 à décembre 2026).'
AS WITH days AS (
    SELECT explode(sequence(DATE '2024-11-01', DATE '2026-12-31', INTERVAL 1 DAY)) AS d
)

SELECT
    d AS calendar_date,
    year(d) AS year,
    quarter(d) AS quarter,
    month(d) AS month,
    element_at(
        array(
            'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
            'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
        ),
        month(d)
    ) AS month_name,
    date_format(d, 'yyyy-MM') AS year_month,
    weekofyear(d) AS iso_week,
    ((dayofweek(d) + 5) % 7) + 1 AS day_of_week,
    element_at(
        array('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'),
        ((dayofweek(d) + 5) % 7) + 1
    ) AS day_name,
    dayofweek(d) IN (1, 7) AS is_weekend,
    d IN (
        DATE '2024-11-01', DATE '2024-11-11', DATE '2024-12-25',
        DATE '2025-01-01', DATE '2025-04-21', DATE '2025-05-01', DATE '2025-05-08', DATE '2025-05-29',
        DATE '2025-06-09', DATE '2025-07-14', DATE '2025-08-15', DATE '2025-11-01', DATE '2025-11-11',
        DATE '2025-12-25', DATE '2026-01-01', DATE '2026-04-06', DATE '2026-05-01', DATE '2026-05-08',
        DATE '2026-05-14', DATE '2026-05-25', DATE '2026-07-14', DATE '2026-08-15', DATE '2026-11-01',
        DATE '2026-11-11', DATE '2026-12-25'
    ) AS is_public_holiday
FROM days;
