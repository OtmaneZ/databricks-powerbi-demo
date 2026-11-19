"""Règles du rapport tirées des tests dans Power BI Desktop (démo négoce, puis cette démo)."""

import json
import re
from pathlib import Path

import build_report

PAGES = Path(build_report.RAPPORT) / "pages"
VISUELS = sorted(PAGES.glob("*/visuals/*/visual.json"))
MODELE = Path(build_report.RACINE) / "powerbi" / "DecDemo.SemanticModel" / "definition" / "tables"

# Largeur moyenne d'un caractère en Segoe UI 9 pt, majorée, et hauteur d'une ligne de tableau.
LARGEUR_CARACTERE_9PT = 6.0
HAUTEUR_LIGNE = 22
MARGES_VERTICALES = 16
HAUTEUR_TITRE = 24


def _charger(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _visuels_de_type(type_: str) -> list[tuple[Path, dict]]:
    return [(c, _charger(c)) for c in VISUELS if _charger(c)["visual"]["visualType"] == type_]


def test_rapport_genere_a_jour(tmp_path, monkeypatch):
    """Les fichiers versionnés sont ceux que produit scripts/build_report.py."""
    avant = {c: c.read_bytes() for c in Path(build_report.RAPPORT).rglob("*.json")}
    build_report.main()
    apres = {c: c.read_bytes() for c in Path(build_report.RAPPORT).rglob("*.json")}
    assert avant == apres


def test_cartes_a_une_seule_valeur():
    """Desktop ignore la grille d'une carte à plusieurs valeurs et rogne les valeurs."""
    cartes = _visuels_de_type("cardVisual")
    assert len(cartes) == 2 * (2 + 10)
    for chemin, contenu in cartes:
        projections = contenu["visual"]["query"]["queryState"]["Data"]["projections"]
        assert len(projections) == 1, chemin.parent.name


def test_cartes_kpi_en_mesures_texte():
    """La VM de test est en en-US : les valeurs sont mises en forme en français par FORMAT."""
    textes = (MODELE / "Mesures.tmdl").read_text(encoding="utf-8")
    for _, contenu in _visuels_de_type("cardVisual"):
        nom = contenu["visual"]["query"]["queryState"]["Data"]["projections"][0]["field"]["Measure"]["Property"]
        assert nom.startswith(("Carte ", "Titre ", "Synthèse ")), nom
        if nom.startswith("Carte "):
            bloc = textes.split(f"measure '{nom}'")[1].split("\n\t///")[0]
            assert '"fr-FR"' in bloc or "Publiées sous UNKNOWN" in bloc, nom


def test_filtres_de_rang_bornes_des_deux_cotes():
    """Un rang vide passe un filtre « ≤ 6 » : chaque filtre de rang a aussi une borne basse."""
    filtres_de_rang = 0
    for chemin in VISUELS:
        for filtre in _charger(chemin).get("filterConfig", {}).get("filters", []):
            mesure = filtre["field"].get("Measure", {}).get("Property", "")
            if not mesure.startswith("Rang "):
                continue
            filtres_de_rang += 1
            condition = filtre["filter"]["Where"][0]["Condition"]
            assert "And" in condition, chemin.parent.name
            bornes = {
                condition["And"][cote]["Comparison"]["ComparisonKind"]: condition["And"][cote]["Comparison"]["Right"][
                    "Literal"
                ]["Value"]
                for cote in ("Left", "Right")
            }
            assert bornes == {2: "1D", 4: f"{build_report.RANG_MAX}D"}, chemin.parent.name
    assert filtres_de_rang == 2


def test_rangs_neutralisent_chaque_colonne_de_regroupement():
    """Dans un tableau groupé sur plusieurs colonnes, le rang retire le filtre de chacune."""
    textes = (MODELE / "Mesures.tmdl").read_text(encoding="utf-8")
    for _chemin, contenu in _visuels_de_type("tableEx"):
        filtres = contenu.get("filterConfig", {}).get("filters", [])
        if not filtres:
            continue
        rang = filtres[0]["field"]["Measure"]["Property"]
        bloc = textes.split(f"measure '{rang}'")[1].split("```")[1]
        for projection in contenu["visual"]["query"]["queryState"]["Values"]["projections"]:
            if "Column" in projection["field"]:
                colonne = projection["field"]["Column"]
                reference = f"REMOVEFILTERS({colonne['Expression']['SourceRef']['Entity']}[{colonne['Property']}])"
                assert reference in bloc, f"{rang} : {reference} manquant"


def test_titres_top_n_neutralisent_le_filtre_du_visuel():
    """Le titre d'un tableau filtré par rang compte les membres sans le filtre de rang."""
    textes = (MODELE / "Mesures.tmdl").read_text(encoding="utf-8")
    for _, contenu in _visuels_de_type("tableEx"):
        if not contenu.get("filterConfig"):
            continue
        titre = contenu["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Measure"]
        bloc = textes.split(f"measure '{titre['Property']}'")[1].split("```")[1]
        for projection in contenu["visual"]["query"]["queryState"]["Values"]["projections"]:
            if "Column" in projection["field"]:
                colonne = projection["field"]["Column"]
                reference = f"REMOVEFILTERS({colonne['Expression']['SourceRef']['Entity']}[{colonne['Property']}])"
                assert reference in bloc, f"{titre['Property']} : {reference} manquant"


def test_tableaux_sans_defilement_et_entetes_sur_une_ligne():
    """Le tableau affiche toutes ses lignes (au plus 6) sans barre de défilement ; en-têtes courts, non renvoyés."""
    tableaux = _visuels_de_type("tableEx")
    assert len(tableaux) == 3
    for chemin, contenu in tableaux:
        hauteur = contenu["position"]["height"]
        besoin = MARGES_VERTICALES + HAUTEUR_TITRE + HAUTEUR_LIGNE * (build_report.RANG_MAX + 1)
        assert hauteur >= besoin, chemin.parent.name
        objets = contenu["visual"]["objects"]
        assert objets["columnHeaders"][0]["properties"]["wordWrap"]["expr"]["Literal"]["Value"] == "false"
        assert objets["total"][0]["properties"]["totals"]["expr"]["Literal"]["Value"] == "false"
        for projection in contenu["visual"]["query"]["queryState"]["Values"]["projections"]:
            assert len(projection.get("displayName", "")) <= 10, projection.get("displayName")


def _libelles_categories() -> dict[tuple[str, str], list[str]]:
    """Valeurs possibles des colonnes utilisées en axe de catégorie."""
    quarantaine = (MODELE / "quarantine_sales.tmdl").read_text(encoding="utf-8")
    motifs = re.findall(r'^\s+[A-Z_]+ = "([^"]+)"', quarantaine, flags=re.MULTILINE)
    return {
        ("dim_store", "region"): ["IDF", "NORD", "EST", "OUEST", "SUD_EST", "SUD_OUEST"],
        ("dim_product", "family"): [
            "Outillage",
            "Matériaux",
            "Peinture",
            "Plomberie",
            "Électricité",
            "Jardin",
            "Menuiserie",
            "Sanitaire",
        ],
        ("quarantine_sales", "reason_label"): motifs,
    }


def test_libelles_d_axe_non_tronques():
    """La marge de l'axe de catégorie laisse la place au libellé le plus long."""
    libelles = _libelles_categories()
    assert len(libelles[("quarantine_sales", "reason_label")]) == 6
    barres = _visuels_de_type("clusteredBarChart")
    assert barres
    for chemin, contenu in barres:
        champ = contenu["visual"]["query"]["queryState"]["Category"]["projections"][0]["field"]["Column"]
        cle = (champ["Expression"]["SourceRef"]["Entity"], champ["Property"])
        axe = contenu["visual"]["objects"]["categoryAxis"][0]["properties"]
        facteur = int(axe["maxMarginFactor"]["expr"]["Literal"]["Value"].rstrip("L")) / 100
        largeur_utile = contenu["position"]["width"] - 24
        plus_long = max(len(texte) for texte in libelles[cle]) * LARGEUR_CARACTERE_9PT
        assert plus_long <= facteur * largeur_utile, f"{chemin.parent.name} : {cle} {plus_long} px"


def test_titres_de_visuels_calcules_en_dax():
    for chemin in VISUELS:
        contenu = _charger(chemin)
        type_ = contenu["visual"]["visualType"]
        if type_ in ("cardVisual", "slicer"):
            continue
        titre = contenu["visual"]["visualContainerObjects"]["title"][0]["properties"]
        assert "Measure" in titre["text"]["expr"], chemin.parent.name
        assert titre["text"]["expr"]["Measure"]["Property"].startswith("Titre "), chemin.parent.name
