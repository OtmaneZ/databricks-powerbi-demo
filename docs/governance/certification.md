# Certification d'un data product gold

Projet de démonstration. Les données sont 100 % fictives.

Un data product certifié est la source de référence pour ses indicateurs. Un rapport ou une analyse qui publie un chiffre officiel le lit dans une table certifiée, et nulle part ailleurs.

Le statut est porté par le tag système Unity Catalog `system.certification_status`. Il prend deux valeurs : `certified` ou `deprecated`. Il est visible dans Catalog Explorer et dans `information_schema.table_tags`.

## 1. Critères

Tous les critères sont obligatoires. Un critère non tenu bloque la certification.

| # | Critère | Comment le vérifier |
|---|---|---|
| 1 | Data owner métier nommé | Tag `data_owner` |
| 2 | Data steward nommé | Tag `data_steward` |
| 3 | Owner technique nommé | Tag `technical_owner`. Cible : propriétaire Unity Catalog = un groupe (pas de groupes de compte sur Free Edition) |
| 4 | `COMMENT` sur la table et sur chaque colonne | Requête sur `information_schema.columns` (voir `standards.md`) |
| 5 | Grain et clés documentés | Fiche data product. `PRIMARY KEY` informative sur les dimensions |
| 6 | Expectations définies sur la table et en amont | Définition dans le pipeline |
| 7 | Expectations respectées au dernier run | Métriques du pipeline : taux de rejet sous le seuil fixé par le data steward |
| 8 | Lignes rejetées traçables | Table de quarantaine `ops.quarantine_<domaine>` |
| 9 | Sécurité ligne si la donnée est régionale | Row filter `ops.rf_region` posé, test de lecture par groupe fait |
| 10 | Pas de donnée personnelle, ou données masquées | Tag `contains_pii = false`, ou masques de colonne en place |
| 11 | Accès accordés à des groupes, en lecture | `SHOW GRANTS ON TABLE …` |
| 12 | Lineage visible dans Unity Catalog | Catalog Explorer, onglet Lineage : sources jusqu'au bronze |
| 13 | Fiche data product à jour | Copie remplie de `docs/templates/fiche-data-product.md` |
| 14 | Fréquence et SLA de rafraîchissement définis | Tag `refresh`, SLA écrit dans la fiche |
| 15 | Dernier run réussi | Historique du job `dec_demo_platform` |

Contrôle rapide des tags d'une table :

```sql
SELECT tag_name, tag_value
FROM dec_dev.information_schema.table_tags
WHERE schema_name = 'gold' AND table_name = 'fct_sales';
```

## 2. Processus de certification

| Étape | Qui | Quoi |
|---|---|---|
| 1. Demande | Data owner ou référent BI du métier | Ouvre la demande avec la fiche data product remplie |
| 2. Préparation | Équipe plateforme data | Complète tags, `COMMENT`, expectations, RLS, grants. Coche la checklist dans la pull request |
| 3. Revue métier | Data steward | Valide définitions, mesures, seuils de qualité |
| 4. Revue conformité | Responsable data governance | Vérifie données personnelles, sécurité, documentation |
| 5. Décision | Responsable data governance, avec l'accord du data owner | Approuve la pull request |
| 6. Application | Équipe plateforme data | Fusion, déploiement, puis le job pose le tag |
| 7. Communication | Équipe plateforme data | Prévient les référents BI. Met à jour la fiche |

Comment le tag est posé : la valeur `'system.certification_status' = 'certified'` est écrite dans `sql/governance/20_data_products.sql`. La tâche `publish_data_products` du job `dec_demo_platform` l'applique après chaque rafraîchissement du pipeline. Le statut est donc versionné et relu comme du code.

Dans la démo, la vérification des critères est manuelle. Un contrôle automatique des critères avant pose du tag est une Cible (non implémenté dans la démo).

## 3. Dépréciation et retrait

Déclencheurs :

- un critère n'est plus tenu de façon durable (échecs répétés, taux de rejet hors seuil, owner parti) ;
- le data product est remplacé par un autre ;
- la source est décommissionnée ;
- un incident de sécurité touche la table.

Étapes :

1. Le responsable data governance décide, après avis du data owner.
2. Pull request : la valeur passe à `'deprecated'` dans `sql/governance/20_data_products.sql`. Le `COMMENT` de la table indique le remplaçant et la date de retrait.
3. Les référents BI sont prévenus. Ils migrent leurs rapports avant la date de retrait.
4. À la date prévue, la table est supprimée du pipeline.

En cas de fuite de données, on coupe d'abord l'accès (incident N3), puis on traite la certification à la revue suivante.

## 4. Exemple : `gold.fct_sales`

Les valeurs de tags ci-dessous sont celles définies dans `sql/governance/20_data_products.sql`. Le 19/11/2026, après exécution du job `dec_demo_platform` sur `dec_dev`, `information_schema.table_tags` renvoie `system.certification_status = certified` pour les six tables gold.

| # | Critère | État dans la démo |
|---|---|---|
| 1 | Data owner | `data_owner = Direction Commerce` |
| 2 | Data steward | `data_steward = Contrôle de gestion` |
| 3 | Owner technique | `technical_owner = Équipe plateforme data`. Propriétaire groupe : Cible |
| 4 | Documentation | `COMMENT` sur la table et sur les 19 colonnes (contrôlé sur `dec_dev`) |
| 5 | Grain et clés | Une ligne par ligne de ticket (`ticket_id`, `line_no`). Clés vers les quatre dimensions |
| 6 | Expectations | En gold : `price_consistent_with_catalog` (drop), `product_in_catalog` (warn). En amont dans `silver.sales` : quatre règles drop, une warn |
| 7 | Respect au dernier run | Run du 19/11/2026 : `price_consistent_with_catalog` a écarté 11 lignes (incident de Metz), `product_in_catalog` a signalé 4 205 lignes conservées en `UNKNOWN` |
| 8 | Traçabilité des rejets | `ops.quarantine_sales` |
| 9 | Sécurité ligne | `ops.rf_region` sur la colonne `region` |
| 10 | Données personnelles | `contains_pii = false`. `customer_id` est un pseudonyme |
| 11 | Accès | Free Edition : `account users` en lecture sur `gold`. Cible : groupes `dec_analysts_national` et `dec_region_*` |
| 12 | Lineage | À contrôler dans Catalog Explorer |
| 13 | Fiche | Exemple rempli dans `docs/templates/fiche-data-product.md` |
| 14 | Rafraîchissement | `refresh = quotidien`. SLA à fixer avec le data owner |
| 15 | Dernier run | Job `dec_demo_platform` réussi le 19/11/2026 (gouvernance, pipeline, publication) |

Décision : `certified`, valeur écrite dans `sql/governance/20_data_products.sql` et appliquée par la tâche `publish_data_products`.

Points de vigilance notés dans la fiche : les produits absents du catalogue sont gardés sous `UNKNOWN` sans marge, et les lignes au prix incohérent sont exclues du chiffre d'affaires.
