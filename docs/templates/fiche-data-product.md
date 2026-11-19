# Modèle : fiche data product

Projet de démonstration. Les données sont 100 % fictives.

Une fiche par data product gold. Elle est remplie par l'équipe plateforme avec le data steward, puis relue avec la pull request de certification (`docs/governance/certification.md`). Remplacer chaque `<…>`. Écrire « aucun » plutôt que laisser un champ vide.

---

## Fiche : `<catalog>.gold.<table>`

### Identité

| Champ | Valeur |
|---|---|
| Nom complet | `<catalog>.gold.<table>` |
| Domaine (tag `domain`) | `<domaine>` |
| Description en une phrase | `<ce que la table permet de mesurer>` |
| Statut (`system.certification_status`) | `<certified, deprecated, ou en préparation>` |
| Date de la fiche | `<JJ/MM/AAAA>` |

### Responsables

| Rôle | Nom (service ou groupe, pas de personne) |
|---|---|
| Data owner (`data_owner`) | `<direction métier>` |
| Data steward (`data_steward`) | `<équipe>` |
| Owner technique (`technical_owner`) | `<équipe>` |
| Référent BI | `<équipe>` |

### Contenu

| Champ | Valeur |
|---|---|
| Grain (une ligne = …) | `<…>` |
| Clé unique | `<colonnes>` |
| Clés vers les dimensions | `<colonne → gold.dim_…>` |
| Mesures et formules | `<mesure = formule>` |
| Membres techniques | `<UNKNOWN, ANONYMOUS… et leur sens>` |
| Profondeur d'historique | `<…>` |

### Alimentation

| Champ | Valeur |
|---|---|
| Sources | `<tables silver et systèmes d'origine>` |
| Pipeline et job | `<pipeline>`, `<job>` |
| Fréquence (tag `refresh`) | `<quotidien, hebdomadaire…>` |
| SLA de disponibilité | `<heure ou délai, validé par le data owner>` |

### Qualité

| Règle | Couche | Sévérité | Ce qui se passe | Seuil d'alerte |
|---|---|---|---|---|
| `<nom_expectation>` | `<silver ou gold>` | `<warn, drop, fail>` | `<…>` | `<…>` |

Table de quarantaine : `<catalog>.ops.quarantine_<domaine>`.

### Sécurité

| Champ | Valeur |
|---|---|
| Données personnelles (`contains_pii`) | `<true ou false, et pourquoi>` |
| Sécurité ligne | `<row filter et colonne, ou aucune>` |
| Groupes ayant accès | `<groupes, en lecture>` |

### Usage et limites

- Consommateurs : `<rapports, équipes>`
- Requête d'exemple : `<SQL>`
- Limites connues : `<liste>`

### Historique

| Date | Changement | Pull request |
|---|---|---|
| `<JJ/MM/AAAA>` | `<…>` | `<lien>` |

---

## Exemple rempli : `gold.fct_sales`

### Identité et responsables

| Champ | Valeur |
|---|---|
| Nom complet | `dec_prod.gold.fct_sales` (`dec_dev` en développement) |
| Domaine | `ventes` |
| Description | Ventes en caisse à la ligne de ticket. Source de référence du chiffre d'affaires net et de la marge brute |
| Statut | `certified` |
| Data owner | Direction Commerce |
| Data steward | Contrôle de gestion |
| Owner technique | Équipe plateforme data |

### Contenu

| Champ | Valeur |
|---|---|
| Grain | Une ligne par ligne de ticket de caisse |
| Clé unique | `ticket_id`, `line_no` (pas de contrainte déclarée sur les faits) |
| Clés vers les dimensions | `sale_date` → `gold.dim_date`, `store_id` → `gold.dim_store`, `product_id` → `gold.dim_product`, `customer_id` → `gold.dim_customer` |
| Mesures | `quantity` ; `net_amount` = quantité × prix unitaire × (1 − remise) ; `cost_amount` = quantité × coût unitaire en vigueur ; `gross_margin` = `net_amount` − `cost_amount` |
| Membres techniques | `product_id = UNKNOWN` : référence absente du catalogue à la date de vente. `customer_id = ANONYMOUS` : vente sans carte de fidélité |
| Stockage | Vue matérialisée, `CLUSTER BY AUTO` |

### Alimentation

- Sources : `bronze.sales` (caisse) → `silver.sales`, enrichi de `silver.stores` (région), `silver.products_history` (prix et coût en vigueur à la date de vente, SCD2) et `silver.customers` (segment).
- Pipeline `dec_demo_etl`, job `dec_demo_platform`. Fréquence : `refresh = quotidien`. SLA : à fixer avec la Direction Commerce.

### Qualité

| Règle | Couche | Sévérité | Ce qui se passe |
|---|---|---|---|
| `store_id_present` | silver | drop | Ligne exclue, motif `STORE_MISSING` |
| `quantity_positive` | silver | drop | Ligne exclue, motif `QUANTITY_NOT_POSITIVE` |
| `sold_at_valid` | silver | drop | Ligne exclue, motif `SOLD_AT_INVALID` |
| `unit_price_positive` | silver | drop | Ligne exclue, motif `UNIT_PRICE_NOT_POSITIVE` |
| `discount_in_range` | silver | warn | Ligne gardée, comptée dans les métriques |
| `price_consistent_with_catalog` | gold | drop | Prix > 1,5 × prix catalogue : ligne exclue, motif `PRICE_INCONSISTENT_WITH_CATALOG` |
| `product_in_catalog` | gold | warn | Ligne gardée sous `UNKNOWN`, motif `PRODUCT_NOT_IN_CATALOG` |

Quarantaine : `ops.quarantine_sales`. La colonne `is_excluded_from_gold` distingue les lignes exclues des lignes gardées.

### Sécurité

- `contains_pii = false`. `customer_id` est un pseudonyme ; nom, email et téléphone restent en silver, masqués.
- Row filter `ops.rf_region` sur `region`, alimenté par `ops.security_region_access`.
- Accès cible : `dec_analysts_national` (toutes régions), `dec_region_<région>` (sa région).

### Usage

Consommateurs : modèle Power BI en Import (prévu), contrôle de gestion, analystes.

```sql
SELECT region, date_trunc('MONTH', sale_date) AS sale_month,
       sum(net_amount) AS net_sales, sum(gross_margin) AS gross_margin
FROM dec_prod.gold.fct_sales
GROUP BY ALL;
```

### Limites connues

- Produit inconnu : la vente compte dans le CA, mais `cost_amount` et `gross_margin` sont NULL. La marge totale est sous-estimée. `source_product_id` garde la référence reçue.
- Prix incohérent : la ligne est exclue du CA. Un vrai changement de prix absent du catalogue produit le même effet ; vérifier la quarantaine.
- Quantité nulle ou négative : ligne rejetée. Suivre les retours demanderait une règle dédiée.
- Remise hors plage : ligne gardée, absente de la quarantaine.
- Vente anonyme : segment `PARTICULIER` par défaut. Le segment PRO peut être sous-estimé.
- Power BI en Import sur Free Edition, sans SSO : le row filter ne s'applique pas lecteur par lecteur. La RLS se fera côté Power BI, depuis la même table d'habilitations (prévu).
