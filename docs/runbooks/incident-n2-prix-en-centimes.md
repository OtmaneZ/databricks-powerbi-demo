# Runbook : CA d'un magasin nul ou anormal sur une journée (prix reçus en centimes)

| Champ | Valeur |
|---|---|
| Niveau | N2 (équipe plateforme data) |
| Data product concerné | `gold.fct_sales` |
| Contrôle déclencheur | `price_consistent_with_catalog` (gold) |
| Cas de référence | Magasin de Metz (`S016`), journée du 14/10/2026, rejoué dans la démo le 19/11/2026 |

Ce runbook a été exécuté de bout en bout sur l'environnement `dec_dev`. Les chiffres cités sont les résultats réels de cette exécution sur les données fictives de la démo.

## 1. Symptôme

Un contrôleur de gestion signale que le rapport des ventes affiche un CA nul pour le magasin de Metz le 14/10/2026, alors que le magasin était ouvert.

Sans contrôle qualité, le symptôme aurait été inverse et plus grave : un CA de 68,5 k€ au lieu de 0,7 k€ pour la journée, soit 100 fois la réalité, propagé dans tous les rapports.

## 2. Impact

- **Périmètre** : un magasin, une journée, 11 lignes de tickets.
- **Données** : le CA publié est temporairement incomplet (0 € au lieu de 685,31 €). Aucun chiffre faux n'est publié.
- **Utilisateurs** : direction régionale Est, contrôle de gestion.
- **Gravité** : faible, car l'écart est contenu et signalé. Elle serait forte sans le contrôle : le CA de la région et de l'enseigne serait faussé.

## 3. Détection

Trois signaux, du plus automatique au plus manuel :

1. **Métriques du pipeline.** Dans l'onglet Data quality de `dec_demo_etl`, `price_consistent_with_catalog` passe de 0 à 11 lignes rejetées.
2. **Table de quarantaine.** Elle contient de nouvelles lignes au motif `PRICE_INCONSISTENT_WITH_CATALOG`.
3. **Signalement d'un utilisateur** (le cas de ce runbook).

## 4. Diagnostic

### Étape 1 : confirmer que les lignes sont en quarantaine

```sql
SELECT quarantine_reason, store_id, cast(sold_at AS DATE) AS sale_date, count(*) AS lines,
       round(avg(unit_price / list_price_at_sale), 1) AS price_ratio
FROM dec_dev.ops.quarantine_sales
WHERE quarantine_reason = 'PRICE_INCONSISTENT_WITH_CATALOG'
GROUP BY ALL
ORDER BY lines DESC;
```

Résultat : 11 lignes, magasin `S016`, le 14/10/2026, avec `price_ratio = 100.0`.

**Lecture** : un ratio de 100 exactement, sur toutes les lignes d'un même magasin et d'un même jour, signe un problème d'unité (centimes au lieu d'euros), pas une erreur de saisie ponctuelle.

### Étape 2 : vérifier que l'anomalie est isolée

```sql
SELECT store_id, count(*) AS lines
FROM dec_dev.ops.quarantine_sales
WHERE quarantine_reason = 'PRICE_INCONSISTENT_WITH_CATALOG'
  AND cast(sold_at AS DATE) = DATE '2026-10-14'
GROUP BY store_id;
```

Résultat : seul `S016` est concerné. Les 39 autres magasins sont sains ce jour-là, donc le référentiel produits (le prix catalogue) n'est pas en cause.

### Étape 3 : remonter au fichier source

```sql
SELECT DISTINCT source_file, ingested_at
FROM dec_dev.ops.quarantine_sales
WHERE store_id = 'S016' AND cast(sold_at AS DATE) = DATE '2026-10-14';
```

Résultat : un seul fichier de l'export caisse d'octobre (`.../landing/sales/file_month=2026-10/part-....json`).

### Étape 4 : confirmer dans l'event log

```sql
WITH ev AS (
  SELECT timestamp, explode(from_json(details:flow_progress:data_quality:expectations,
    'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
  FROM event_log(TABLE(dec_dev.gold.fct_sales))
  WHERE event_type = 'flow_progress' AND details:flow_progress:data_quality IS NOT NULL
)
SELECT timestamp, e.name, e.passed_records, e.failed_records
FROM ev
ORDER BY timestamp DESC;
```

Résultat : `price_consistent_with_catalog` avec 11 rejets et 1 421 495 lignes valides.

## 5. Cause racine

L'export caisse du magasin de Metz a transmis les prix unitaires en centimes au lieu d'euros pour la journée du 14/10/2026. Le reste de l'export (tickets, quantités, produits) est correct.

Dans le scénario de la démo, l'hypothèse retenue est un changement de format côté caisse, sur ce seul magasin. Dans un cas réel, la cause se confirme avec l'équipe qui opère le logiciel de caisse.

## 6. Résolution

**Principe : on corrige à la source, pas dans le pipeline.** Une règle « diviser par 100 » ajoutée en dur masquerait le problème et finirait par s'appliquer à tort.

1. Demander à l'équipe caisse un renvoi corrigé des tickets du magasin et de la journée concernés.
2. Déposer le fichier corrigé dans la zone de réception, dans le dossier du mois. Dans la démo, cette étape est simulée par :
   ```bash
   DATABRICKS_CONFIG_PROFILE=dec-demo uv run python -m dec_demo.generate --catalog dec_dev --correct-incident
   ```
3. Relancer le pipeline : `databricks bundle run dec_demo_etl -t dev`. Auto Loader n'ingère que le nouveau fichier.
4. Règle appliquée automatiquement, « le dernier envoi fait foi » : pour une même ligne de ticket, seule la version la plus récente alimente `gold.fct_sales`.
5. Vérifier :
   ```sql
   SELECT count(*) AS lines, sum(net_amount) AS ca
   FROM dec_dev.gold.fct_sales
   WHERE store_id = 'S016' AND sale_date = DATE '2026-10-14';
   ```
   Résultat obtenu : 11 lignes, CA de 685,31 €. Aucune ligne de ticket en double dans `gold.fct_sales`. Le contrôle `price_consistent_with_catalog` repasse à 0 rejet.

Les 11 lignes d'origine restent dans `ops.quarantine_sales` avec `is_latest_version = false`, pour garder l'historique de l'incident.

## 7. Prévention

| Action | Responsable | État |
|---|---|---|
| Garder le contrôle `price_consistent_with_catalog` en mode rejet | Équipe plateforme data | En place |
| Alerte quotidienne si la quarantaine reçoit des lignes `PRICE_INCONSISTENT_WITH_CATALOG` (alerte SQL Databricks) | Équipe plateforme data | Cible (non implémenté dans la démo) |
| Contrat d'interface avec l'équipe caisse : prix en euros, deux décimales, contrôle à l'émission | Data owner Commerce, équipe caisse | Cible |
| Ajouter ce cas aux tests de non-régression du pipeline | Équipe plateforme data | Cible |

## 8. Communication

- **À l'ouverture** : message au contrôle de gestion et à la direction régionale Est. « Le CA de Metz du 14/10 est provisoirement incomplet : 11 lignes ont été écartées par un contrôle qualité. Aucun chiffre faux n'a été publié. Correction demandée à la source. »
- **À la clôture** : même liste de diffusion. « Données corrigées et republiées le <date>. CA du 14/10 pour Metz : 685,31 €. »
- **Revue mensuelle** : l'incident est présenté à la revue des data products, avec la mesure de prévention retenue.
