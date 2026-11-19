# Test dans Power BI Desktop (Windows)

Procédure en sept étapes, à suivre dans l'ordre sur un poste Windows avec PowerShell. Aucun identifiant Databricks n'est nécessaire : le modèle lit les fichiers Parquet de `powerbi\data\`, exportés de la couche gold. Pour chaque étape : ce qui doit s'afficher, et ce qu'il faut relever si ce n'est pas le cas.

Toutes les valeurs attendues ci-dessous sont calculées en SQL sur Databricks par `scripts/expected_values.py`. Sauf mention contraire, elles portent sur l'année 2026 (janvier à octobre), toutes régions.

Prérequis : le commit qui ajoute `powerbi/` est poussé sur GitHub, et Power BI Desktop est à jour (projets PBIP, modèle TMDL et rapport PBIR).

## 1. Télécharger le dépôt dans C:\databricks-powerbi-demo

Dans PowerShell :

```powershell
$dest = "C:\databricks-powerbi-demo"
$zip = Join-Path $env:TEMP "databricks-powerbi-demo.zip"
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
Invoke-WebRequest -Uri "https://github.com/OtmaneZ/databricks-powerbi-demo/archive/refs/heads/main.zip" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $env:TEMP -Force
Move-Item (Join-Path $env:TEMP "databricks-powerbi-demo-main") $dest
Remove-Item $zip
Get-ChildItem "$dest\powerbi\data" | Select-Object Name, Length
```

**Résultat attendu** : `powerbi\data` contient 8 fichiers `.parquet` et `manifest.json`. Le plus gros, `fct_sales.parquet`, pèse environ 35 Mo.

**À relever sinon** : le message d'erreur PowerShell complet.

## 2. Ouvrir le projet et actualiser

```powershell
Start-Process "C:\databricks-powerbi-demo\powerbi\DecDemo.pbip"
```

1. Le paramètre `DossierDonnees` vaut déjà `C:\databricks-powerbi-demo\powerbi\data\` : aucune saisie n'est nécessaire.
2. Accueil > Actualiser.

**Résultat attendu** : l'ouverture et l'actualisation se terminent sans message d'erreur. Dans la vue Tableau, le nombre de lignes affiché en bas de l'écran pour chaque table est :

| Table | Lignes |
|---|---|
| fct_sales | 1 421 506 |
| fct_stock_weekly | 1 040 000 |
| quarantine_sales | 6 358 |
| dim_date | 791 |
| dim_store | 40 |
| dim_product | 3 001 |
| dim_customer | 60 001 |
| security_region_access | 8 |
| security_user_group | 10 |

**À relever sinon** : le texte exact du message d'erreur (ou une capture), l'étape où il apparaît (ouverture ou actualisation) et la table concernée.

## 3. Exécuter la requête de validation

Dans PowerShell, copier la requête dans le presse-papiers :

```powershell
Get-Content "C:\databricks-powerbi-demo\tests\validation.dax" -Raw -Encoding UTF8 | Set-Clipboard
```

Dans Desktop, vue Requête DAX : coller, puis Exécuter.

**Résultat attendu** : deux résultats.

- Le premier affiche **Contrôles = 386** et **KO = 0**.
- Le second détaille chaque contrôle (colonnes Cas, Mesure, Attendu, Obtenu, Écart, Statut), lignes KO en premier.

Les 386 contrôles couvrent 8 cas (toutes années, 2024, 2025, 2026, 2026 région NORD, 2026 région EST, 2026 NORD Jardin avril, 2026 Magasin Metz octobre) : montants, taux, nombres, ainsi que les titres, synthèses et cartes de cinq cas.

**À relever sinon** : si la requête échoue, le message d'erreur complet ; si KO est supérieur à 0, toutes les lignes KO du second résultat (bouton de copie du tableau de résultats).

## 4. Parcourir la page Ventes et ruptures

Le segment Année est sur 2026, le segment Région n'a aucune sélection.

**Résultat attendu** :

- Titre : « En 2026, le CA net atteint 62,9 M€, en hausse de 5,6 % sur un an à période comparable ».
- Synthèse : « Évolution la plus faible : région NORD (+4,5 %). Taux de rupture le plus élevé : région NORD (3,6 %). Données fictives. »
- Cinq cartes, chacune avec son libellé au-dessus de la valeur et une ligne de détail en dessous, sans « … » :

| Carte | Valeur | Détail |
|---|---|---|
| CA net | 62,9 M€ | +5,6 % sur un an |
| Marge brute | 19,7 M€ | 31,4 % du CA net |
| Panier moyen | 250,65 € | 250 762 tickets |
| Part du CA PRO | 47,2 % | Particuliers : 52,8 % |
| Taux de rupture | 2,3 % | 19 733 sur 860 000 relevés |

- Colonnes mensuelles titrées « CA net Jardin par mois, sur un an : évolution la plus faible en mai (-8 %) », deux séries (2026 en bleu, N-1 en gris), mois de janvier à octobre.
- Tableau titré « 500 produits en rupture : les 6 plus fréquents » : six lignes exactement, en-têtes Produit, Famille, Ruptures sur une ligne, sans barre de défilement ni total.
- Barres « Taux de rupture par région : NORD en tête (3,6 %) ».
- Barres « Évolution du CA net sur un an par région : NORD en dernier (+4,5 %) ».
- Barres « Par famille : Jardin en dernier (+1,3 %) », huit familles, sans la famille Inconnu ; noms de famille entiers.

Puis sélectionner la région NORD dans le segment Région :

- Titre : « En 2026, le CA net atteint 10,3 M€, en hausse de 4,5 % sur un an à période comparable ».
- Colonnes mensuelles : « CA net Jardin par mois, sur un an : évolution la plus faible en avril (-62 %) », avec un creux net en avril et en mai (rupture d'approvisionnement).

Revenir ensuite à aucune sélection de région.

**À relever sinon** : une capture de la page et, pour chaque visuel en erreur, le message affiché par « Afficher les détails ».

## 5. Parcourir la page Qualité et incident de prix

Année 2026, aucune région sélectionnée.

**Résultat attendu** :

- Titre : « En 2026, 2 717 lignes en quarantaine, dont 954 exclues des ventes publiées et 11 au prix incohérent ».
- Synthèse : « Principal incident de prix : Magasin Metz le 14/10/2026, prix encaissés 100 fois le prix catalogue. Taux de rejet : 0,15 %. Données fictives. »

| Carte | Valeur | Détail |
|---|---|---|
| Lignes en quarantaine | 2 717 | Taux de rejet : 0,15 % |
| Exclues des ventes publiées | 954 | 35 % de la quarantaine |
| Prix incohérents | 11 | Prix reçus × 100,0 le catalogue |
| CA erroné écarté | 68 531 € | Au prix catalogue : 685 € |
| Produits inconnus | 1 763 | Publiées sous UNKNOWN, sans marge |

- Colonnes « Lignes en quarantaine par mois : pic en mai (375 lignes) ».
- Barres « Par motif : Produit absent du catalogue en tête (1 763 lignes) », libellés de motif entiers.
- Barres « Taux de rejet par région : EST en tête (0,12 %) ».
- Tableau « Prix incohérents : 1 cas (un magasin, un jour) » : une ligne, Magasin Metz, 14/10/2026, 11 lignes, 68 531 €.
- Tableau « Contrôles du pipeline : 4 motifs observés » : quatre lignes, sans barre de défilement.

**À relever sinon** : une capture de la page et le message de chaque visuel en erreur.

## 6. Tester la sécurité ligne (RLS)

Modélisation > Afficher en tant que : cocher **Autre utilisateur**, saisir l'adresse, cocher le rôle **Habilitations régionales**, puis OK. Les comptes sont fictifs ; ils correspondent aux groupes de `ops.security_region_access`.

| Adresse | Résultat attendu |
|---|---|
| `direction.nord@example.com` | Le segment Région ne propose que NORD. Titre Ventes : « En 2026, le CA net atteint 10,3 M€, en hausse de 4,5 % sur un an à période comparable ». Page Qualité : tableau « Prix incohérents : aucun cas sur la sélection » (l'incident de Metz est dans la région EST). |
| `direction.est@example.com` | Le segment Région ne propose que EST. Titre Ventes : « En 2026, le CA net atteint 9,9 M€, en hausse de 5,1 % sur un an à période comparable ». Page Qualité : l'incident de Metz est visible. |
| `direction.nord-est@example.com` | Le segment Région propose EST et NORD (compte membre de deux groupes). |
| `admin.plateforme@example.com` | Les six régions sont visibles. Titre Ventes identique à celui de l'étape 4. |
| `inconnu@example.com` | Aucune donnée : titre Ventes « Aucune vente sur la sélection ». |

Revenir ensuite à l'affichage normal (Arrêter l'affichage).

**À relever sinon** : pour chaque adresse, une capture de la page Ventes et ruptures.

## 7. Fermer sans enregistrer, supprimer le dossier et vérifier

1. Fermer Power BI Desktop en choisissant **Ne pas enregistrer** : le test ne doit modifier aucun fichier.
2. Dans PowerShell :

```powershell
Remove-Item "C:\databricks-powerbi-demo" -Recurse -Force
Test-Path "C:\databricks-powerbi-demo"
Test-Path (Join-Path $env:TEMP "databricks-powerbi-demo.zip")
```

**Résultat attendu** : les deux commandes `Test-Path` affichent `False`.

**À relever sinon** : le message de `Remove-Item` (un fichier encore ouvert par Desktop bloque la suppression : fermer Desktop puis relancer la commande).
