# Modèle opérationnel du Data Expertise Centre

Projet de démonstration. Les données sont 100 % fictives.

Le Data Expertise Centre (DEC) construit la plateforme, fixe les standards et accompagne les métiers. Son objectif final : **les équipes internes opèrent seules**. Le passage de relais se prépare dès le premier jour.

## 1. Rôles

| Rôle | Responsabilités | Dans la démo |
|---|---|---|
| Équipe plateforme data | Construit et opère la plateforme : pipeline, job, bundles, sécurité technique. Support N2 et N3. Standards techniques | Groupe `dec_platform_admins`, tag `technical_owner` |
| Responsable data governance | Porte les standards, la certification, les revues d'accès et la conformité des données personnelles | Décide de la certification |
| Data owners métier | Directions responsables d'un domaine : définitions, priorités, validation des accès | Tag `data_owner` (Direction Commerce, Direction Supply Chain…) |
| Data stewards | Qualité au quotidien : seuils, analyse de la quarantaine, définitions des indicateurs | Tag `data_steward` (Contrôle de gestion…) |
| Référents BI des métiers | Rapports Power BI de leur métier, support N1, relais des formations | Consommateurs de `gold` |
| IT / infrastructure | Annuaire et groupes, systèmes sources, réseau, licences Power BI | Synchronisation des groupes (cible) |
| Groupe international | Cadre commun : standards et plateformes du groupe, arbitrages d'architecture, partage entre pays | Consulté sur les choix structurants |

## 2. RACI

R = réalise, A = décide et rend compte (un seul par ligne), C = consulté, I = informé.

| Activité | Plateforme | Gouvernance | Data owner | Data steward | Référent BI | IT | Groupe |
|---|---|---|---|---|---|---|---|
| Nouveau data product | R | C | A | C | C | I | I |
| Évolution d'un data product | R | I | A | C | C | - | - |
| Demande d'accès | R | I | A | - | I | R | - |
| Certification d'un data product | R | A | C | C | I | - | I |
| Incident N1 (usage, rapport) | I | - | I | C | A/R | - | - |
| Incident N2 (données, run en échec) | A/R | I | I | C | I | - | - |
| Incident N3 (plateforme, sécurité) | A/R | C | I | - | I | R | C |
| Changement de schéma à la source | R | I | A | C | I | R | - |
| Déploiement Power BI | C | I | A | C | R | C | - |
| Revue de sécurité et des accès | R | A | C | - | I | C | I |
| Transfert de compétences | R | A | I | C | C | I | - |

Précisions :

- **Demande d'accès.** Le data owner valide. L'IT ajoute la personne au groupe dans l'annuaire. L'équipe plateforme met à jour `ops.security_region_access` si un nouveau groupe ou une nouvelle région est en jeu. On n'accorde jamais un droit à une personne directement.
- **Changement de schéma à la source.** L'IT prévient avant la livraison. L'équipe plateforme adapte bronze et silver, puis vérifie la quarantaine au premier run.

## 3. Niveaux de support

| Niveau | Qui | Périmètre | Point d'entrée | Escalade si |
|---|---|---|---|---|
| N1 | Référents BI des métiers | Usage des rapports, définition d'un indicateur, « je ne vois pas mes données » | Fiche data product, rapport | La donnée manque ou ne correspond pas à la source |
| N2 | Équipe plateforme data, avec le data steward | Run en échec, lignes rejetées, écart de chiffres, habilitations | `ops.quarantine_sales`, métriques du pipeline, runbooks | Défaut de plateforme, bug éditeur, suspicion de fuite |
| N3 | Équipe plateforme data (experts), IT, support éditeur, groupe international si plateforme commune | Panne de plateforme, sécurité, performance | Event log, historique des runs, support éditeur | - |

Chemin d'escalade : utilisateur → référent BI (N1) → équipe plateforme (N2) → N3.

Exception : une suspicion de fuite de données va directement en N3, avec le responsable data governance. On coupe l'accès d'abord, on analyse ensuite.

Outil de tickets et délais de traitement par niveau : Cible (non implémenté dans la démo), à fixer avec les métiers.

## 4. Rituels

| Rituel | Fréquence | Participants | Entrées | Sorties |
|---|---|---|---|---|
| Triage | Hebdomadaire, 30 min | Équipe plateforme, data stewards, référents BI | Quarantaine par motif, runs en échec, tickets ouverts | Actions assignées, corrections demandées aux sources, runbooks à écrire |
| Revue des data products | Mensuelle, 1 h | Data owners, data stewards, gouvernance, équipe plateforme | Taux de rejet, fraîcheur, demandes d'évolution, statut de certification | Priorités, certifications et dépréciations |
| Revue des accès | Trimestrielle | Gouvernance, data owners, équipe plateforme, IT | Contenu de `ops.security_region_access`, membres des groupes, grants | Droits retirés, colonne `reason` à jour, test de RLS rejoué |

Requête de départ du triage hebdomadaire :

```sql
SELECT quarantine_reason, rejected_at, is_excluded_from_gold, count(*) AS line_count
FROM dec_prod.ops.quarantine_sales
GROUP BY ALL
ORDER BY line_count DESC;
```

Pour la revue des accès, deux points d'attention :

- Le test de RLS se fait avec un compte de chaque groupe régional : il ne doit voir que sa région dans `gold.fct_sales`.
- Un ajout ou un retrait de groupe n'est pas visible tout de suite par `is_member()`. Un délai de propagation a été observé dans la démo. On rejoue le test plus tard avant de conclure.

## 5. Plan de transfert de compétences

Principe : on fait, puis on fait ensemble, puis l'équipe fait et on relit.

| Phase | Format | Contenu | Livrable |
|---|---|---|---|
| 1. Ateliers | 6 ateliers de 2 h, sur la démo | Voir la liste ci-dessous | Supports et exercices dans le repo |
| 2. Pairing | Binôme sur des tickets réels | Un data product, un incident N2, un déploiement | Pull requests co-écrites |
| 3. Runbooks et templates | Rédigés par l'équipe interne, relus | Incidents fréquents, fiche data product | `docs/runbooks/`, `docs/templates/` |
| 4. Coaching | L'équipe fait, le consultant relit | Revue des pull requests, animation des rituels | Rituels animés par l'équipe |
| 5. Autonomie | Le consultant n'intervient plus que sur demande | - | Critères de sortie atteints |

Ateliers :

1. Architecture et couches : bronze, silver, gold, ops, Unity Catalog.
2. Pipeline Lakeflow : expectations, quarantaine, event log.
3. Déploiement : Git, pull request, Declarative Automation Bundles, dev puis prod.
4. Sécurité : groupes, row filter, masques, table d'habilitations, tests.
5. Power BI sur gold : modèle en Import, RLS.
6. Gouvernance : certification, fiche data product, rituels.

Critères de sortie (« les équipes internes opèrent seules ») :

- [ ] Un nouveau data product livré de bout en bout par l'équipe interne, seulement relu.
- [ ] Un incident N2 résolu avec un runbook, sans aide.
- [ ] Un déploiement en production fait par l'équipe.
- [ ] Une revue d'accès trimestrielle menée par l'équipe.
- [ ] Les rituels animés par l'équipe pendant un mois.
