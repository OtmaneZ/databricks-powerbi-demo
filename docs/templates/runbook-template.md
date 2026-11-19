# Modèle : runbook d'incident

Projet de démonstration. Les données sont 100 % fictives.

Un runbook par type d'incident récurrent. Il doit permettre à une personne qui ne connaît pas le sujet de traiter l'incident seule. Copier ce fichier dans `docs/runbooks/`, le nommer `<domaine>-<symptome>.md`, et remplacer chaque `<…>`.

Règles d'écriture : des phrases courtes, des étapes numérotées, des requêtes prêtes à copier. Si une étape demande un jugement, dire qui décide.

---

# Runbook : `<titre court, formulé comme le symptôme>`

| Champ | Valeur |
|---|---|
| Niveau de support | `<N1, N2 ou N3>` |
| Objets concernés | `<catalog.schema.table, pipeline, job>` |
| Propriétaire du runbook | `<équipe>` |
| Dernière revue | `<JJ/MM/AAAA>` |

## 1. Symptôme

> Ce que voit l'utilisateur ou ce que dit l'alerte, avec ses mots. Une ou deux phrases. Un symptôme par runbook.

`<Exemple : « Le CA d'hier est plus bas que prévu dans le rapport Ventes. »>`

## 2. Impact

> Qui est touché, sur quoi, depuis quand. Choisir une gravité.

| Gravité | Définition |
|---|---|
| Critique | Chiffre faux publié, ou fuite de données. Escalade immédiate |
| Majeure | Data product en retard ou incomplet, sans contournement |
| Mineure | Anomalie limitée, contournement possible |

- Data products touchés : `<…>`
- Rapports et utilisateurs touchés : `<…>`
- Gravité : `<…>`

## 3. Détection

> Comment l'incident est remonté. Si c'est un utilisateur qui l'a vu en premier, noter quelle alerte aurait dû le voir avant.

- [ ] Notification d'échec du job `dec_demo_platform`
- [ ] Métriques d'expectations du pipeline `dec_demo_etl`
- [ ] Hausse d'un motif dans `ops.quarantine_sales` (triage hebdomadaire)
- [ ] Signalement N1 par un référent BI

## 4. Diagnostic

> Étapes dans l'ordre, du plus probable au moins probable. Chaque étape dit quoi regarder et quoi conclure.

1. `<étape>` → si `<constat>`, aller à `<étape ou section 6>`.
2. `<étape>` → …

Requêtes utiles (remplacer `<catalog>` par `dec_dev` ou `dec_prod`) :

Lignes en quarantaine par motif :

```sql
SELECT quarantine_reason, rejected_at, is_excluded_from_gold, count(*) AS line_count
FROM <catalog>.ops.quarantine_sales
GROUP BY ALL
ORDER BY line_count DESC;
```

Fichier source à l'origine des rejets :

```sql
SELECT source_file, quarantine_reason, count(*) AS line_count
FROM <catalog>.ops.quarantine_sales
GROUP BY ALL
ORDER BY line_count DESC;
```

Métriques d'expectations du dernier run du pipeline :

```sql
SELECT e.dataset, e.name, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
FROM (
  SELECT explode(from_json(details:flow_progress.data_quality.expectations,
    'array<struct<name: string, dataset: string, passed_records: bigint, failed_records: bigint>>')) AS e
  FROM event_log(TABLE(<catalog>.silver.sales))
  WHERE event_type = 'flow_progress'
    AND origin.update_id = (SELECT max_by(origin.update_id, timestamp)
                            FROM event_log(TABLE(<catalog>.silver.sales))
                            WHERE event_type = 'create_update')
)
GROUP BY ALL
ORDER BY failed DESC;
```

Habilitations d'un groupe (incident « je ne vois pas mes données ») :

```sql
SELECT * FROM <catalog>.ops.security_region_access WHERE principal_group = '<groupe>';
-- À exécuter par l'utilisateur concerné :
SELECT is_account_group_member('<groupe>') OR is_member('<groupe>') AS in_group;
```

Attention : un changement de groupe n'est pas visible tout de suite par `is_member()`. Rejouer le test plus tard avant de conclure.

## 5. Cause racine

> Distinguer le déclencheur (ce qui a changé) de la cause racine (pourquoi rien ne l'a arrêté). Poser « pourquoi ? » jusqu'à trouver une cause sur laquelle on peut agir.

- Déclencheur : `<…>`
- Cause racine : `<…>`

## 6. Résolution

> Séparer la correction immédiate de la correction définitive. Indiquer qui valide avant de relancer.

Correction immédiate :

1. `<…>`
2. Relancer et vérifier : `databricks bundle run dec_demo_platform -t <cible>`, puis rejouer la requête de diagnostic.

Correction définitive : `<changement de code, demande au système source…>`, livrée par pull request.

Une réinitialisation complète (full refresh) d'une streaming table relit toute la source. Elle demande l'accord de l'équipe plateforme.

## 7. Prévention

> Ce qui empêchera l'incident de revenir, ou le fera détecter plus tôt.

- [ ] Nouvelle expectation ou seuil ajusté (validé par le data steward)
- [ ] Nouveau test (`tests/`)
- [ ] Alerte ou rituel à adapter
- [ ] Standard ou fiche data product à mettre à jour

## 8. Communication

> Qui prévenir, quand, par quel canal. Prévenir tôt, même sans la cause.

| Moment | Destinataires | Message |
|---|---|---|
| Détection | Référents BI, data owner | Ce qui est touché, ce qu'il faut éviter d'utiliser |
| Résolution | Mêmes destinataires | Ce qui est corrigé, à partir de quand les chiffres sont fiables |
| Clôture | Rituel de triage | Cause racine et prévention |

Modèle de message : « `<data product>` est `<retardé, incomplet>` depuis `<date heure>`. Impact : `<…>`. Prochaine information : `<heure>`. »
