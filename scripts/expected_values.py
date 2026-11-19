"""Calcule en SQL sur Databricks les valeurs attendues des mesures du modèle Power BI et les
enregistre dans tests/expected/*.json (lues par scripts/build_validation_dax.py).

Usage : DATABRICKS_CONFIG_PROFILE=dec-demo uv run python scripts/expected_values.py --catalog dec_dev

Les requêtes lisent les mêmes tables que l'export Parquet (gold et ops). Elles reproduisent
la sémantique des mesures DAX : N-1 calculé seulement sur une période précédente complète,
dates postérieures à la dernière vente ignorées, filtre famille sans effet sur la
quarantaine (pas de relation), lignes sans magasin exclues dès qu'un filtre porte sur les
magasins, résultat vide de DIVIDE pour un dénominateur vide ou nul. Les textes attendus
(titres, synthèses, cartes) suivent la mise en forme française de FORMAT(..., "fr-FR").
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = RACINE / "tests" / "expected"
REGIONS = ["EST", "IDF", "NORD", "OUEST", "SUD_EST", "SUD_OUEST"]
LIBELLES_MOTIFS = {
    "STORE_MISSING": "Magasin absent",
    "QUANTITY_NOT_POSITIVE": "Quantité nulle ou négative",
    "SOLD_AT_INVALID": "Date de vente invalide",
    "UNIT_PRICE_NOT_POSITIVE": "Prix nul ou négatif",
    "PRICE_INCONSISTENT_WITH_CATALOG": "Prix incohérent avec le catalogue",
    "PRODUCT_NOT_IN_CATALOG": "Produit absent du catalogue",
}
PRIX = "PRICE_INCONSISTENT_WITH_CATALOG"

CAS = [
    ("toutes_annees", "Toutes années", {}, False),
    ("2024_total", "2024 total", {"annee": 2024}, True),
    ("2025_total", "2025 total", {"annee": 2025}, True),
    ("2026_total", "2026 total", {"annee": 2026}, True),
    ("2026_region_nord", "2026 région NORD", {"annee": 2026, "region": "NORD"}, True),
    ("2026_region_est", "2026 région EST", {"annee": 2026, "region": "EST"}, True),
    (
        "2026_nord_jardin_avril",
        "2026 NORD Jardin avril",
        {"annee": 2026, "region": "NORD", "famille": "Jardin", "mois": 4},
        False,
    ),
    ("2026_metz_octobre", "2026 Magasin Metz octobre", {"annee": 2026, "magasin": "Magasin Metz", "mois": 10}, False),
]


# --------------------------------------------------------------------------- mise en forme française
def fr(valeur: float, decimales: int) -> str:
    """FORMAT(valeur, "#,0.00…", "fr-FR"), espaces insécables remplacés par des espaces."""
    quantum = Decimal(1).scaleb(-decimales)
    arrondi = Decimal(repr(float(valeur))).quantize(quantum, rounding=ROUND_HALF_UP)
    texte = f"{arrondi:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")


def pct(valeur: float, decimales: int) -> str:
    return fr(valeur * 100, decimales) + " %"


def pct_signe(valeur: float, decimales: int) -> str:
    """FORMAT(valeur, "+0.0 %;-0.0 %;0.0 %", "fr-FR")."""
    if valeur == 0:
        return pct(0, decimales)
    return ("+" if valeur > 0 else "-") + pct(abs(valeur), decimales)


def divide(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


# --------------------------------------------------------------------------- requêtes
class Source:
    def __init__(self, spark, catalogue: str):
        self.spark = spark
        self.c = catalogue
        self.derniere_vente = self.scalaire(f"SELECT max(sale_date) FROM {self.c}.gold.fct_sales")
        self.dates_modele = {
            ligne[0] for ligne in spark.sql(f"SELECT calendar_date FROM {self.c}.gold.dim_date").collect()
        }

    def scalaire(self, sql: str):
        return self.spark.sql(sql).first()[0]

    def lignes(self, sql: str) -> list:
        return self.spark.sql(sql).collect()

    @staticmethod
    def conditions(filtres: dict, dates: list | None, avec_famille: bool = True, sans_dates: bool = False) -> str:
        morceaux = ["1 = 1"]
        if dates is not None:
            liste = ", ".join(f"DATE'{d.isoformat()}'" for d in sorted(dates)) or "NULL"
            morceaux.append(f"d.calendar_date IN ({liste})")
        elif not sans_dates:
            if "annee" in filtres:
                morceaux.append(f"d.year = {filtres['annee']}")
            if "mois" in filtres:
                morceaux.append(f"d.month = {filtres['mois']}")
        if "region" in filtres:
            morceaux.append(f"s.region = '{filtres['region']}'")
        if "magasin" in filtres:
            morceaux.append(f"s.store_name = '{filtres['magasin']}'")
        if avec_famille and "famille" in filtres:
            morceaux.append(f"p.family = '{filtres['famille']}'")
        return " AND ".join(morceaux)

    def dates_contexte(self, filtres: dict) -> list[dt.date]:
        cond = ["1 = 1"]
        if "annee" in filtres:
            cond.append(f"year = {filtres['annee']}")
        if "mois" in filtres:
            cond.append(f"month = {filtres['mois']}")
        cond.append(f"calendar_date <= DATE'{self.derniere_vente.isoformat()}'")
        return [
            r[0] for r in self.lignes(f"SELECT calendar_date FROM {self.c}.gold.dim_date WHERE {' AND '.join(cond)}")
        ]

    def dates_n1(self, filtres: dict) -> list[dt.date] | None:
        """Dates de la période N-1 (DATEADD -1 an), ou None si elle n'est pas complète."""
        dates = self.dates_contexte(filtres)
        decalees = [d.replace(year=d.year - 1) for d in dates]
        presentes = [d for d in decalees if d in self.dates_modele]
        if not dates or len(presentes) != len(dates):
            return None
        return presentes

    def ventes(self, filtres: dict, dates=None, groupe: str | None = None, famille: str | None = None) -> dict:
        cle = groupe or "'tout'"
        cond = self.conditions(filtres, dates, avec_famille=famille is None)
        if famille:
            cond += f" AND p.family = '{famille}'"
        sql = f"""
            SELECT {cle} AS k,
                   sum(f.net_amount) AS net, sum(f.cost_amount) AS cout, sum(f.gross_margin) AS marge,
                   sum(CASE WHEN f.product_id <> 'UNKNOWN' THEN f.net_amount END) AS net_ref,
                   sum(f.quantity) AS qte, count(*) AS lignes, count(DISTINCT f.ticket_id) AS tickets,
                   sum(CASE WHEN f.customer_segment = 'PRO' THEN f.net_amount END) AS net_pro
            FROM {self.c}.gold.fct_sales f
            JOIN {self.c}.gold.dim_date d ON f.sale_date = d.calendar_date
            JOIN {self.c}.gold.dim_store s ON f.store_id = s.store_id
            JOIN {self.c}.gold.dim_product p ON f.product_id = p.product_id
            WHERE {cond}
            GROUP BY 1"""
        return {r["k"]: r.asDict() for r in self.lignes(sql)}

    def stocks(self, filtres: dict, groupe: str | None = None) -> dict:
        cle = groupe or "'tout'"
        sql = f"""
            SELECT {cle} AS k, count(*) AS releves, count_if(k.is_out_of_stock) AS ruptures
            FROM {self.c}.gold.fct_stock_weekly k
            JOIN {self.c}.gold.dim_date d ON k.snapshot_date = d.calendar_date
            JOIN {self.c}.gold.dim_store s ON k.store_id = s.store_id
            JOIN {self.c}.gold.dim_product p ON k.product_id = p.product_id
            WHERE {self.conditions(filtres, None)}
            GROUP BY 1"""
        return {r["k"]: r.asDict() for r in self.lignes(sql)}

    def quarantaine(self, filtres: dict, groupe: str | None = None) -> dict:
        cle = groupe or "'tout'"
        sql = f"""
            SELECT {cle} AS k, count(*) AS lignes,
                   count_if(q.is_excluded_from_gold) AS exclues,
                   count_if(q.quarantine_reason = '{PRIX}') AS prix,
                   count_if(q.quarantine_reason = 'PRODUCT_NOT_IN_CATALOG') AS inconnus,
                   sum(CASE WHEN q.quarantine_reason = '{PRIX}'
                            THEN q.quantity * CAST(round(q.unit_price, 4) AS DECIMAL(19, 4)) END) AS ca_errone,
                   sum(CASE WHEN q.quarantine_reason = '{PRIX}'
                            THEN q.quantity * CAST(round(q.list_price_at_sale, 4) AS DECIMAL(19, 4))
                       END) AS ca_catalogue
            FROM {self.c}.ops.quarantine_sales q
            LEFT JOIN {self.c}.gold.dim_store s ON q.store_id = s.store_id
            LEFT JOIN {self.c}.gold.dim_date d ON to_date(q.sold_at) = d.calendar_date
            WHERE {self.conditions(filtres, None, avec_famille=False)}
            GROUP BY 1"""
        return {r["k"]: r.asDict() for r in self.lignes(sql)}


# --------------------------------------------------------------------------- mesures
def nul_si_zero(valeur):
    return None if valeur in (None, 0) else valeur


def flottant(valeur):
    return None if valeur is None else float(valeur)


def mesures_numeriques(src: Source, filtres: dict) -> dict:
    v = src.ventes(filtres).get("tout", {})
    net = flottant(v.get("net"))
    lignes = nul_si_zero(v.get("lignes"))
    tickets = nul_si_zero(v.get("tickets"))
    dates_n1 = src.dates_n1(filtres)
    n1 = None
    jardin_n1 = None
    if dates_n1 is not None:
        n1 = flottant(src.ventes(filtres, dates=dates_n1).get("tout", {}).get("net"))
        jardin_n1 = flottant(src.ventes(filtres, dates=dates_n1, famille="Jardin").get("tout", {}).get("net"))
    jardin = flottant(src.ventes(filtres, famille="Jardin").get("tout", {}).get("net"))
    ecart = None if n1 is None or net is None else net - n1
    k = src.stocks(filtres).get("tout", {})
    releves = nul_si_zero(k.get("releves"))
    ruptures = nul_si_zero(k.get("ruptures"))
    q = src.quarantaine(filtres).get("tout", {})
    exclues = nul_si_zero(q.get("exclues"))
    ca_errone = flottant(q.get("ca_errone"))
    ca_catalogue = flottant(q.get("ca_catalogue"))
    return {
        "CA net": ("montant", net),
        "Coût d'achat": ("montant", flottant(v.get("cout"))),
        "Marge brute": ("montant", flottant(v.get("marge"))),
        "CA net produits référencés": ("montant", flottant(v.get("net_ref"))),
        "Taux de marge brute (%)": ("taux", divide(flottant(v.get("marge")), flottant(v.get("net_ref")))),
        "Quantité vendue": ("nombre", nul_si_zero(v.get("qte"))),
        "# Lignes de vente": ("nombre", lignes),
        "# Tickets": ("nombre", tickets),
        "Panier moyen": ("ratio", divide(net, tickets)),
        "Part du CA PRO (%)": ("taux", divide(flottant(v.get("net_pro")), net)),
        "CA net Jardin": ("montant", jardin),
        "CA net N-1": ("montant", n1),
        "CA net écart N-1": ("montant", ecart),
        "CA net évol. N-1 (%)": ("taux", divide(ecart, n1)),
        "CA net Jardin N-1": ("montant", jardin_n1),
        "CA net Jardin évol. N-1 (%)": (
            "taux",
            None if jardin_n1 is None else divide((jardin or 0) - jardin_n1, jardin_n1),
        ),
        "# Relevés de stock": ("nombre", releves),
        "# Ruptures": ("nombre", ruptures),
        "Taux de rupture (%)": ("taux", divide(ruptures, releves)),
        "# Lignes en quarantaine": ("nombre", nul_si_zero(q.get("lignes"))),
        "# Lignes exclues de gold": ("nombre", exclues),
        "# Lignes au prix incohérent": ("nombre", nul_si_zero(q.get("prix"))),
        "# Lignes produit inconnu": ("nombre", nul_si_zero(q.get("inconnus"))),
        "CA erroné écarté": ("montant", ca_errone),
        "CA au prix catalogue des lignes écartées": ("montant", ca_catalogue),
        "Ratio prix encaissé sur catalogue": ("ratio", divide(ca_errone, ca_catalogue)),
        "Taux de rejet (%)": ("taux", None if exclues is None else divide(exclues, exclues + (lignes or 0))),
    }


def regions_contexte(filtres: dict) -> list[str]:
    if "region" in filtres:
        return [filtres["region"]]
    if "magasin" in filtres:
        return ["EST"] if filtres["magasin"] == "Magasin Metz" else REGIONS
    return REGIONS


def evolutions_par(src: Source, filtres: dict, colonne: str) -> dict:
    """Évolution du CA net sur un an par membre de colonne (region ou family)."""
    dates_n1 = src.dates_n1(filtres)
    if dates_n1 is None:
        return {}
    groupe = {"region": "s.region", "family": "p.family"}[colonne]
    n = src.ventes(filtres, groupe=groupe)
    n1 = src.ventes(filtres, dates=dates_n1, groupe=groupe)
    resultat = {}
    for cle, valeurs in n.items():
        base = flottant(n1.get(cle, {}).get("net"))
        net = flottant(valeurs["net"])
        if base:
            resultat[cle] = (net - base) / base
    return resultat


def textes(src: Source, filtres: dict, m: dict) -> dict:
    annee = filtres.get("annee")
    val = {nom: valeur for nom, (_, valeur) in m.items()}
    t = {}

    # Page Ventes et ruptures
    ca, evol = val["CA net"], val["CA net évol. N-1 (%)"]
    ca_texte = None if ca is None else fr(ca / 1_000_000, 1) + " M€"
    if ca is None:
        t["Titre ventes"] = "Aucune vente sur la sélection"
    elif evol is None:
        t["Titre ventes"] = (
            f"En {annee}, le CA net atteint {ca_texte} (pas de comparaison sur un an : période précédente incomplète)"
        )
    else:
        sens = "en hausse" if evol >= 0 else "en baisse"
        t["Titre ventes"] = (
            f"En {annee}, le CA net atteint {ca_texte}, {sens} de {pct(abs(evol), 1)} sur un an à période comparable"
        )

    evol_regions = {r: e for r, e in evolutions_par(src, filtres, "region").items() if r in regions_contexte(filtres)}
    stocks_regions = src.stocks(filtres, groupe="s.region")
    taux_rupture = {
        r: divide(nul_si_zero(v["ruptures"]), v["releves"]) for r, v in stocks_regions.items() if v["ruptures"]
    }
    if evol_regions:
        faible = min(evol_regions, key=lambda r: (evol_regions[r], r))
        texte_evol = f"Évolution la plus faible : région {faible} ({pct_signe(evol_regions[faible], 1)})."
        t["Titre évolution par région"] = (
            f"Évolution du CA net sur un an par région : {faible} en dernier ({pct_signe(evol_regions[faible], 1)})"
        )
    else:
        texte_evol = "Évolution sur un an non calculable (période précédente incomplète)."
        t["Titre évolution par région"] = "Évolution du CA net sur un an par région"
    if taux_rupture:
        forte = min(taux_rupture, key=lambda r: (-taux_rupture[r], r))
        texte_rupture = f" Taux de rupture le plus élevé : région {forte} ({pct(taux_rupture[forte], 1)})."
        t["Titre ruptures par région"] = f"Taux de rupture par région : {forte} en tête ({pct(taux_rupture[forte], 1)})"
    else:
        texte_rupture = " Pas de relevé de stock sur la période."
        t["Titre ruptures par région"] = "Taux de rupture par région"
    t["Synthèse ventes"] = texte_evol + texte_rupture + " Données fictives."

    evol_familles = {f: e for f, e in evolutions_par(src, filtres, "family").items() if f != "Inconnu"}
    if evol_familles:
        faible = min(evol_familles, key=lambda f: (evol_familles[f], f))
        t["Titre évolution par famille"] = f"Par famille : {faible} en dernier ({pct_signe(evol_familles[faible], 1)})"
    else:
        t["Titre évolution par famille"] = "Évolution du CA net sur un an par famille"

    noms_mois = {r[0]: r[1] for r in src.lignes(f"SELECT DISTINCT month, month_name FROM {src.c}.gold.dim_date")}
    evol_mois = {}
    for mois in range(1, 13):
        filtre_mois = {**filtres, "mois": mois}
        dates_n1 = src.dates_n1(filtre_mois)
        jardin = flottant(src.ventes(filtre_mois, famille="Jardin").get("tout", {}).get("net"))
        if dates_n1 is None or jardin is None:
            continue
        jardin_n1 = flottant(src.ventes(filtre_mois, dates=dates_n1, famille="Jardin").get("tout", {}).get("net"))
        if jardin_n1 is None:
            continue
        evol_mois[mois] = divide(jardin - jardin_n1, jardin_n1)
    if evol_mois:
        pire = min(evol_mois, key=lambda k: (evol_mois[k], k))
        signe = "+" if evol_mois[pire] > 0 else ("-" if evol_mois[pire] < 0 else "")
        t["Titre Jardin mensuel"] = (
            "CA net Jardin par mois, sur un an : évolution la plus faible en "
            f"{noms_mois[pire]} ({signe}{fr(abs(evol_mois[pire]) * 100, 0)} %)"
        )
    else:
        t["Titre Jardin mensuel"] = "CA net Jardin par mois"

    produits = src.scalaire(
        f"""SELECT count(DISTINCT k.product_id) FROM {src.c}.gold.fct_stock_weekly k
            JOIN {src.c}.gold.dim_date d ON k.snapshot_date = d.calendar_date
            JOIN {src.c}.gold.dim_store s ON k.store_id = s.store_id
            JOIN {src.c}.gold.dim_product p ON k.product_id = p.product_id
            WHERE {src.conditions(filtres, None)} AND k.is_out_of_stock"""
    )
    if produits == 0:
        t["Titre produits en rupture"] = "Aucun produit en rupture sur la période"
    elif produits == 1:
        t["Titre produits en rupture"] = "1 produit en rupture"
    elif produits <= 6:
        t["Titre produits en rupture"] = f"{produits} produits en rupture"
    else:
        t["Titre produits en rupture"] = f"{fr(produits, 0)} produits en rupture : les 6 plus fréquents"

    # Page Qualité et incident de prix
    lignes_q = val["# Lignes en quarantaine"]
    exclues = val["# Lignes exclues de gold"] or 0
    prix = val["# Lignes au prix incohérent"] or 0
    if lignes_q is None:
        t["Titre qualité"] = f"En {annee}, aucune ligne en quarantaine"
    else:
        libelle = " ligne en quarantaine, dont " if lignes_q == 1 else " lignes en quarantaine, dont "
        t["Titre qualité"] = (
            f"En {annee}, {fr(lignes_q, 0)}{libelle}{fr(exclues, 0)} exclues des ventes publiées et "
            f"{fr(prix, 0)} au prix incohérent"
        )

    incidents = src.lignes(
        f"""SELECT s.store_name, d.calendar_date, count(*) AS n,
                   sum(q.quantity * CAST(round(q.unit_price, 4) AS DECIMAL(19, 4))) AS errone,
                   sum(q.quantity * CAST(round(q.list_price_at_sale, 4) AS DECIMAL(19, 4))) AS catalogue
            FROM {src.c}.ops.quarantine_sales q
            LEFT JOIN {src.c}.gold.dim_store s ON q.store_id = s.store_id
            LEFT JOIN {src.c}.gold.dim_date d ON to_date(q.sold_at) = d.calendar_date
            WHERE {src.conditions(filtres, None, avec_famille=False)} AND q.quarantine_reason = '{PRIX}'
            GROUP BY 1, 2"""
    )
    if incidents:
        principal = sorted(incidents, key=lambda r: (-r["n"], r["store_name"] or "", r["calendar_date"]))[0]
        date = principal["calendar_date"]
        ratio = float(principal["errone"]) / float(principal["catalogue"])
        texte_incident = (
            f"Principal incident de prix : {principal['store_name']} le {date:%d/%m/%Y}, "
            f"prix encaissés {fr(ratio, 0)} fois le prix catalogue."
        )
    else:
        texte_incident = "Aucun prix incohérent sur la sélection."
    taux_rejet = val["Taux de rejet (%)"]
    texte_rejet = "" if taux_rejet is None else f" Taux de rejet : {pct(taux_rejet, 2)}."
    t["Synthèse qualité"] = texte_incident + texte_rejet + " Données fictives."

    nombre_incidents = len(incidents)
    if nombre_incidents == 0:
        t["Titre incidents de prix"] = "Prix incohérents : aucun cas sur la sélection"
    elif nombre_incidents == 1:
        t["Titre incidents de prix"] = "Prix incohérents : 1 cas (un magasin, un jour)"
    elif nombre_incidents <= 6:
        t["Titre incidents de prix"] = f"Prix incohérents : {nombre_incidents} cas magasin et jour"
    else:
        t["Titre incidents de prix"] = (
            f"Prix incohérents : {nombre_incidents} cas magasin et jour, les 6 plus importants"
        )

    par_mois = src.quarantaine(filtres, groupe="d.month")
    par_mois = {k: v["lignes"] for k, v in par_mois.items() if k is not None and v["lignes"]}
    if par_mois:
        pic = min(par_mois, key=lambda k: (-par_mois[k], k))
        t["Titre quarantaine mensuelle"] = (
            f"Lignes en quarantaine par mois : pic en {noms_mois[pic]} ({fr(par_mois[pic], 0)} lignes)"
        )
    else:
        t["Titre quarantaine mensuelle"] = "Lignes en quarantaine par mois"

    par_motif = {}
    for motif, valeurs in src.quarantaine(filtres, groupe="q.quarantine_reason").items():
        par_motif[LIBELLES_MOTIFS.get(motif, motif)] = valeurs["lignes"]
    if par_motif:
        premier = min(par_motif, key=lambda k: (-par_motif[k], k))
        t["Titre quarantaine par motif"] = f"Par motif : {premier} en tête ({fr(par_motif[premier], 0)} lignes)"
        motifs = len(par_motif)
        t["Titre contrôles"] = f"Contrôles du pipeline : {motifs}" + (
            " motif observé" if motifs == 1 else " motifs observés"
        )
    else:
        t["Titre quarantaine par motif"] = "Lignes en quarantaine par motif"
        t["Titre contrôles"] = "Contrôles du pipeline : aucune anomalie"

    rejets = {}
    lignes_region = src.ventes(filtres, groupe="s.region")
    for region, valeurs in src.quarantaine(filtres, groupe="s.region").items():
        if region is None or not valeurs["exclues"]:
            continue
        exclues_r = valeurs["exclues"]
        rejets[region] = exclues_r / (exclues_r + lignes_region.get(region, {}).get("lignes", 0))
    if rejets:
        fort = min(rejets, key=lambda r: (-rejets[r], r))
        t["Titre rejet par région"] = f"Taux de rejet par région : {fort} en tête ({pct(rejets[fort], 2)})"
    else:
        t["Titre rejet par région"] = "Taux de rejet par région"

    # Cartes KPI
    def ou_nd(valeur, texte):
        return "n.d." if valeur is None else texte

    marge, taux_marge = val["Marge brute"], val["Taux de marge brute (%)"]
    panier, tickets = val["Panier moyen"], val["# Tickets"]
    part_pro, taux_rupture_global = val["Part du CA PRO (%)"], val["Taux de rupture (%)"]
    t["Carte CA net"] = ou_nd(ca, ca_texte)
    t["Carte CA net évol."] = (
        "n.d. sur un an" if evol is None else ("-" if evol < 0 else "+") + pct(abs(evol), 1) + " sur un an"
    )
    t["Carte marge brute"] = ou_nd(marge, marge is not None and fr(marge / 1_000_000, 1) + " M€")
    t["Carte marge brute taux"] = ou_nd(taux_marge, taux_marge is not None and pct(taux_marge, 1) + " du CA net")
    t["Carte panier moyen"] = ou_nd(panier, panier is not None and fr(panier, 2) + " €")
    t["Carte tickets"] = ou_nd(tickets, tickets is not None and fr(tickets, 0) + " tickets")
    t["Carte part PRO"] = ou_nd(part_pro, part_pro is not None and pct(part_pro, 1))
    t["Carte part particuliers"] = ou_nd(part_pro, part_pro is not None and "Particuliers : " + pct(1 - part_pro, 1))
    t["Carte taux de rupture"] = ou_nd(
        taux_rupture_global, taux_rupture_global is not None and pct(taux_rupture_global, 1)
    )
    releves = val["# Relevés de stock"]
    t["Carte ruptures"] = (
        "Aucun relevé de stock" if releves is None else f"{fr(val['# Ruptures'] or 0, 0)} sur {fr(releves, 0)} relevés"
    )
    t["Carte lignes en quarantaine"] = fr(lignes_q or 0, 0)
    t["Carte taux de rejet"] = "Taux de rejet : " + (pct(taux_rejet, 2) if taux_rejet is not None else "0,00 %")
    t["Carte lignes exclues"] = fr(exclues, 0)
    part_exclue = divide(exclues, lignes_q)
    t["Carte part exclue"] = ou_nd(part_exclue, part_exclue is not None and pct(part_exclue, 0) + " de la quarantaine")
    t["Carte prix incohérents"] = fr(prix, 0)
    ratio = val["Ratio prix encaissé sur catalogue"]
    t["Carte ratio prix"] = "Aucun écart de prix" if ratio is None else f"Prix reçus × {fr(ratio, 1)} le catalogue"
    t["Carte CA erroné"] = fr(val["CA erroné écarté"] or 0, 0) + " €"
    t["Carte CA catalogue"] = (
        "Au prix catalogue : " + fr(val["CA au prix catalogue des lignes écartées"] or 0, 0) + " €"
    )
    t["Carte produits inconnus"] = fr(val["# Lignes produit inconnu"] or 0, 0)
    t["Carte produits inconnus détail"] = "Publiées sous UNKNOWN, sans marge"
    return t


def arrondi(type_: str, valeur):
    if valeur is None:
        return None
    if type_ == "nombre":
        return int(valeur)
    return round(float(valeur), 10)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Valeurs attendues des mesures Power BI, calculées en SQL.")
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(RACINE / "src"))
    from dec_demo.generate import get_spark

    src = Source(get_spark(), args.catalog)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    for ancien in DOSSIER.glob("*.json"):
        ancien.unlink()
    total = 0
    for fichier, cas, filtres, avec_textes in CAS:
        numeriques = mesures_numeriques(src, filtres)
        mesures = [
            {"mesure": nom, "type": type_, "attendu": arrondi(type_, valeur)}
            for nom, (type_, valeur) in sorted(numeriques.items())
        ]
        if avec_textes:
            mesures += [
                {"mesure": nom, "type": "texte", "attendu": texte}
                for nom, texte in sorted(textes(src, filtres, numeriques).items())
            ]
        contenu = {"cas": cas, "filtres": filtres, "mesures": mesures}
        (DOSSIER / f"{fichier}.json").write_text(
            json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        total += len(mesures)
        print(f"{fichier}.json : {len(mesures)} valeurs")
    print(f"Total : {total} valeurs attendues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
