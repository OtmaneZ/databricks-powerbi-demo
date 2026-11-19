"""Génère le rapport Power BI (format PBIR) dans powerbi/DecDemo.Report/definition/.

Usage : python scripts/build_report.py

Les deux pages sont décrites dans PAGES, sur une trame commune (titre, synthèse, deux
segments, cinq cartes KPI sur deux lignes, cinq visuels). Le script réécrit report.json,
version.json, pages/pages.json et chaque page.json et visual.json. Les noms de pages et
de visuels sont dérivés de leur position dans la description : une régénération sans
changement de description produit des fichiers identiques.

Règles appliquées ici, tirées des tests dans Power BI Desktop :
- une seule valeur par carte KPI (cardVisual), en mesure texte mise en forme en français ;
- filtres de rang bornés des deux côtés (entre 1 et N) ;
- en-têtes de tableau sur une ligne, tableau assez haut pour toutes ses lignes ;
- libellés d'axe de catégorie non tronqués (marge d'axe élargie) ;
- titres de visuels calculés par des mesures.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
RAPPORT = RACINE / "powerbi" / "DecDemo.Report" / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
THEME = "DecSobre-7c41e2a9.json"
BASE_THEME = "Fluent2-CY26SU10"

BLEU, ROUGE, GRIS, TEXTE, TEXTE_SECONDAIRE, FOND = "#1F4E79", "#B42318", "#8A8886", "#252423", "#605E5C", "#F3F2F1"
RANG_MAX = 6

# Trame commune aux deux pages (multiples de 8 px, canevas 1280 x 720).
TITRE = (24, 32, 920, 40)
SYNTHESE = (24, 88, 920, 40)
SEGMENT_ANNEE = (960, 32, 120, 96)
SEGMENT_REGION = (1096, 32, 160, 96)
CARTES_X = (24, 272, 520, 768, 1016)
CARTE_VALEUR_Y, CARTE_VALEUR_H = 144, 56
CARTE_DETAIL_Y, CARTE_DETAIL_H = 200, 40
LARGEUR_CARTE = 240
ZONES = {
    "haut_gauche": (24, 256, 712, 208),
    "haut_droite": (752, 256, 504, 208),
    "bas_gauche": (24, 480, 400, 208),
    "bas_centre": (440, 480, 400, 208),
    "bas_droite": (856, 480, 400, 208),
}

PAGES = [
    {
        "nom": "Ventes et ruptures",
        "titre": "Titre ventes",
        "synthese": "Synthèse ventes",
        "cartes": [
            ("CA net", "Carte CA net", "Carte CA net évol."),
            ("Marge brute", "Carte marge brute", "Carte marge brute taux"),
            ("Panier moyen", "Carte panier moyen", "Carte tickets"),
            ("Part du CA PRO", "Carte part PRO", "Carte part particuliers"),
            ("Taux de rupture", "Carte taux de rupture", "Carte ruptures"),
        ],
        "visuels": [
            {
                "zone": "haut_gauche",
                "type": "colonnes",
                "categorie": ("dim_date", "month_name"),
                "series": [("CA net Jardin", BLEU), ("CA net Jardin N-1", GRIS)],
                "titre": "Titre Jardin mensuel",
                "unites": 1000,
            },
            {
                "zone": "bas_centre",
                "type": "barres",
                "categorie": ("dim_store", "region"),
                "valeur": "CA net évol. N-1 (%)",
                "titre": "Titre évolution par région",
                "signe": True,
                "infobulles": ["CA net", "CA net N-1"],
            },
            {
                "zone": "bas_gauche",
                "type": "barres",
                "categorie": ("dim_store", "region"),
                "valeur": "Taux de rupture (%)",
                "titre": "Titre ruptures par région",
                "signe": False,
                "infobulles": ["# Ruptures", "# Relevés de stock"],
            },
            {
                "zone": "haut_droite",
                "type": "tableau",
                "colonnes": [
                    ("colonne", "dim_product", "product_name", "Produit"),
                    ("colonne", "dim_product", "family", "Famille"),
                    ("mesure", "Mesures", "# Ruptures", "Ruptures"),
                ],
                "tri": ("# Ruptures", "Descending"),
                "rang": "Rang produit en rupture",
                "titre": "Titre produits en rupture",
            },
            {
                "zone": "bas_droite",
                "type": "barres",
                "categorie": ("dim_product", "family"),
                "valeur": "CA net évol. N-1 (%)",
                "titre": "Titre évolution par famille",
                "signe": True,
                "infobulles": ["CA net", "CA net N-1"],
                "exclure": ("dim_product", "family", "Inconnu"),
            },
        ],
    },
    {
        "nom": "Qualité et incident de prix",
        "titre": "Titre qualité",
        "synthese": "Synthèse qualité",
        "cartes": [
            ("Lignes en quarantaine", "Carte lignes en quarantaine", "Carte taux de rejet"),
            ("Exclues des ventes publiées", "Carte lignes exclues", "Carte part exclue"),
            ("Prix incohérents", "Carte prix incohérents", "Carte ratio prix"),
            ("CA erroné écarté", "Carte CA erroné", "Carte CA catalogue"),
            ("Produits inconnus", "Carte produits inconnus", "Carte produits inconnus détail"),
        ],
        "visuels": [
            {
                "zone": "haut_gauche",
                "type": "colonnes",
                "categorie": ("dim_date", "month_name"),
                "series": [("# Lignes en quarantaine", BLEU)],
                "titre": "Titre quarantaine mensuelle",
                "unites": 1,
            },
            {
                "zone": "haut_droite",
                "type": "barres",
                "categorie": ("quarantine_sales", "reason_label"),
                "valeur": "# Lignes en quarantaine",
                "titre": "Titre quarantaine par motif",
                "signe": False,
                "infobulles": ["# Lignes exclues de gold"],
            },
            {
                "zone": "bas_gauche",
                "type": "barres",
                "categorie": ("dim_store", "region"),
                "valeur": "Taux de rejet (%)",
                "titre": "Titre rejet par région",
                "signe": False,
                "infobulles": ["# Lignes exclues de gold", "# Lignes de vente"],
            },
            {
                "zone": "bas_centre",
                "type": "tableau",
                "colonnes": [
                    ("colonne", "dim_store", "store_name", "Magasin"),
                    ("colonne", "dim_date", "calendar_date", "Jour"),
                    ("mesure", "Mesures", "# Lignes au prix incohérent", "Lignes"),
                    ("mesure", "Mesures", "CA erroné écarté", "CA erroné"),
                ],
                "tri": ("# Lignes au prix incohérent", "Descending"),
                "rang": "Rang incident de prix",
                "titre": "Titre incidents de prix",
            },
            {
                "zone": "bas_droite",
                "type": "tableau",
                "colonnes": [
                    ("colonne", "quarantine_sales", "reason_label", "Motif"),
                    ("colonne", "quarantine_sales", "rejected_at", "Étape"),
                    ("mesure", "Mesures", "# Lignes en quarantaine", "Lignes"),
                ],
                "tri": ("# Lignes en quarantaine", "Descending"),
                "rang": None,
                "titre": "Titre contrôles",
            },
        ],
    },
]


# --------------------------------------------------------------------------- briques JSON
def litteral(valeur: str) -> dict:
    return {"expr": {"Literal": {"Value": valeur}}}


def couleur(code: str) -> dict:
    return {"solid": {"color": litteral(f"'{code}'")}}


def mesure(nom: str, source: str | None = None) -> dict:
    ref = {"Source": source} if source else {"Entity": "Mesures"}
    return {"Measure": {"Expression": {"SourceRef": ref}, "Property": nom}}


def colonne(table: str, nom: str, source: str | None = None) -> dict:
    ref = {"Source": source} if source else {"Entity": table}
    return {"Column": {"Expression": {"SourceRef": ref}, "Property": nom}}


def projection(champ: dict, libelle: str | None = None) -> dict:
    cle = "Measure" if "Measure" in champ else "Column"
    entite = champ[cle]["Expression"]["SourceRef"]["Entity"]
    propriete = champ[cle]["Property"]
    resultat = {"field": champ, "queryRef": f"{entite}.{propriete}", "nativeQueryRef": propriete}
    if libelle:
        resultat["displayName"] = libelle
    return resultat


def identifiant(*morceaux: str) -> str:
    return hashlib.sha1("|".join(morceaux).encode("utf-8")).hexdigest()[:20]


def conteneur(titre_mesure: str | None, alt: str, fond: bool = True, marges=(8, 8, 12, 12)) -> dict:
    haut, bas, gauche, droite = marges
    objets = {
        "background": [{"properties": {"show": litteral("true" if fond else "false")}}],
        "border": [{"properties": {"show": litteral("false")}}],
        "dropShadow": [{"properties": {"show": litteral("false")}}],
        "padding": [
            {
                "properties": {
                    "top": litteral(f"{haut}D"),
                    "bottom": litteral(f"{bas}D"),
                    "left": litteral(f"{gauche}D"),
                    "right": litteral(f"{droite}D"),
                }
            }
        ],
        "visualHeader": [{"properties": {"show": litteral("false")}}],
        "subTitle": [{"properties": {"show": litteral("false")}}],
    }
    if fond:
        objets["background"][0]["properties"].update({"color": couleur("#FFFFFF"), "transparency": litteral("0D")})
    if titre_mesure:
        objets["title"] = [
            {
                "properties": {
                    "show": litteral("true"),
                    "text": {"expr": mesure(titre_mesure)},
                    "titleWrap": litteral("true"),
                    "fontSize": litteral("11D"),
                    "bold": litteral("false"),
                    "fontColor": couleur(TEXTE),
                    "alignment": litteral("'left'"),
                }
            }
        ]
        objets["general"] = [{"properties": {"altText": {"expr": mesure(titre_mesure)}}}]
    else:
        objets["title"] = [{"properties": {"show": litteral("false")}}]
        objets["general"] = [{"properties": {"altText": litteral(f"'{alt}'")}}]
    return objets


def enveloppe(nom: str, rect: tuple[int, int, int, int], ordre: int, visuel: dict, filtres=None) -> dict:
    x, y, largeur, hauteur = rect
    resultat = {
        "$schema": f"{SCHEMA}/visualContainer/2.13.0/schema.json",
        "name": nom,
        "position": {"x": x, "y": y, "z": ordre, "height": hauteur, "width": largeur, "tabOrder": ordre},
        "visual": visuel,
    }
    if filtres:
        resultat["filterConfig"] = {"filters": filtres}
    return resultat


# --------------------------------------------------------------------------- visuels
def carte_texte(mesure_nom: str, taille: int, couleur_texte: str, libelle: str | None, fond: bool) -> dict:
    valeur = {
        "fontSize": litteral(f"{taille}D"),
        "bold": litteral("false"),
        "fontColor": couleur(couleur_texte),
        "horizontalAlignment": litteral("'left'"),
    }
    if not fond:
        valeur["textWrap"] = litteral("true")
    if libelle:
        etiquette = {
            "show": litteral("true"),
            "fontSize": litteral("9D"),
            "fontColor": couleur(TEXTE_SECONDAIRE),
            "position": litteral("'aboveValue'"),
            "horizontalAlignment": litteral("'left'"),
        }
    else:
        etiquette = {"show": litteral("false")}
    marges = (8, 0, 12, 12) if libelle else ((0, 8, 12, 12) if fond else (0, 0, 0, 0))
    return {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [projection(mesure(mesure_nom), libelle)]}}},
        "objects": {
            "value": [{"properties": valeur, "selector": {"id": "default"}}],
            "label": [{"properties": etiquette, "selector": {"id": "default"}}],
            "outline": [{"properties": {"show": litteral("false")}, "selector": {"id": "default"}}],
            "padding": [{"properties": {"paddingUniform": litteral("0D")}, "selector": {"id": "default"}}],
        },
        "visualContainerObjects": conteneur(None, libelle or mesure_nom, fond=fond, marges=marges),
    }


def segment(table: str, nom_colonne: str, entete: str, defaut_annee: int | None) -> dict:
    objets = {
        "data": [{"properties": {"mode": litteral("'HorizontalList'" if defaut_annee else "'Dropdown'")}}],
        "header": [{"properties": {"show": litteral("true"), "text": litteral(f"'{entete}'")}}],
        "selection": [
            {
                "properties": {
                    "singleSelect": litteral("true" if defaut_annee else "false"),
                    "selectAllCheckboxEnabled": litteral("false" if defaut_annee else "true"),
                }
            }
        ],
    }
    if defaut_annee:
        objets["general"] = [
            {
                "properties": {
                    "filter": {
                        "filter": {
                            "Version": 2,
                            "From": [{"Name": "d", "Entity": table, "Type": 0}],
                            "Where": [
                                {
                                    "Condition": {
                                        "In": {
                                            "Expressions": [colonne(table, nom_colonne, "d")],
                                            "Values": [[{"Literal": {"Value": f"{defaut_annee}L"}}]],
                                        }
                                    }
                                }
                            ],
                        }
                    }
                }
            }
        ]
    return {
        "visualType": "slicer",
        "syncGroup": {"groupName": entete, "fieldChanges": True, "filterChanges": True},
        "query": {"queryState": {"Values": {"projections": [projection(colonne(table, nom_colonne))]}}},
        "objects": objets,
        "visualContainerObjects": conteneur(None, f"Segment {entete}", marges=(8, 8, 8, 8)),
    }


def axe_categorie() -> dict:
    return {
        "show": litteral("true"),
        "fontSize": litteral("9D"),
        "labelColor": couleur(TEXTE),
        "maxMarginFactor": litteral("50L"),
    }


def barres(spec: dict) -> dict:
    table, nom_colonne = spec["categorie"]
    valeur = mesure(spec["valeur"])
    zero = {"Literal": {"Value": "0D"}}
    if spec["signe"]:
        remplissage = {
            "expr": {
                "Conditional": {
                    "Cases": [
                        {
                            "Condition": {
                                "Comparison": {
                                    "ComparisonKind": 2,
                                    "Left": valeur,
                                    "Right": zero,
                                }
                            },
                            "Value": {"Literal": {"Value": f"'{BLEU}'"}},
                        },
                        {
                            "Condition": {
                                "Comparison": {
                                    "ComparisonKind": 3,
                                    "Left": valeur,
                                    "Right": zero,
                                }
                            },
                            "Value": {"Literal": {"Value": f"'{ROUGE}'"}},
                        },
                    ]
                }
            }
        }
        point = [
            {
                "properties": {"fill": {"solid": {"color": remplissage}}},
                "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
            }
        ]
    else:
        point = [{"properties": {"fill": couleur(BLEU)}}]
    return {
        "visualType": "clusteredBarChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(colonne(table, nom_colonne))]},
                "Y": {"projections": [projection(valeur)]},
                "Tooltips": {"projections": [projection(mesure(m)) for m in spec["infobulles"]]},
            },
            "sortDefinition": {"sort": [{"field": valeur, "direction": "Descending"}], "isDefaultSort": False},
        },
        "objects": {
            "dataPoint": point,
            "labels": [
                {
                    "properties": {
                        "show": litteral("true"),
                        "color": couleur(TEXTE),
                        "fontSize": litteral("9D"),
                        "labelPosition": litteral("'OutsideEnd'"),
                    }
                }
            ],
            "valueAxis": [{"properties": {"show": litteral("false"), "gridlineShow": litteral("false")}}],
            "categoryAxis": [{"properties": axe_categorie()}],
            "legend": [{"properties": {"show": litteral("false")}}],
        },
        "visualContainerObjects": conteneur(spec["titre"], spec["titre"]),
    }


def colonnes_mensuelles(spec: dict) -> dict:
    table, nom_colonne = spec["categorie"]
    categorie = colonne(table, nom_colonne)
    multi = len(spec["series"]) > 1
    return {
        "visualType": "clusteredColumnChart",
        "query": {
            "queryState": {
                "Category": {"projections": [projection(categorie)]},
                "Y": {"projections": [projection(mesure(nom)) for nom, _ in spec["series"]]},
            },
            "sortDefinition": {"sort": [{"field": categorie, "direction": "Ascending"}], "isDefaultSort": False},
        },
        "objects": {
            "dataPoint": [
                {"properties": {"fill": couleur(code)}, "selector": {"metadata": f"Mesures.{nom}"}}
                for nom, code in spec["series"]
            ],
            "legend": [
                {
                    "properties": {
                        "show": litteral("true" if multi else "false"),
                        "position": litteral("'TopRight'"),
                        "fontSize": litteral("9D"),
                    }
                }
            ],
            "labels": [{"properties": {"show": litteral("false")}}],
            "valueAxis": [
                {
                    "properties": {
                        "show": litteral("true"),
                        "labelDisplayUnits": litteral(f"{spec['unites']}D"),
                        "fontSize": litteral("9D"),
                        "gridlineShow": litteral("true"),
                        "gridlineColor": couleur("#E1DFDD"),
                    }
                }
            ],
            "categoryAxis": [{"properties": {**axe_categorie(), "axisType": litteral("'Categorical'")}}],
        },
        "visualContainerObjects": conteneur(spec["titre"], spec["titre"]),
    }


def tableau(spec: dict) -> dict:
    projections = []
    for genre, table, nom, libelle in spec["colonnes"]:
        champ = mesure(nom) if genre == "mesure" else colonne(table, nom)
        projections.append(projection(champ, libelle))
    mesure_tri, sens = spec["tri"]
    return {
        "visualType": "tableEx",
        "query": {
            "queryState": {"Values": {"projections": projections}},
            "sortDefinition": {"sort": [{"field": mesure(mesure_tri), "direction": sens}], "isDefaultSort": False},
        },
        "objects": {
            "columnHeaders": [
                {
                    "properties": {
                        "autoSizeColumnWidth": litteral("true"),
                        "fontSize": litteral("9D"),
                        "bold": litteral("true"),
                        "fontColor": couleur(TEXTE),
                        "wordWrap": litteral("false"),
                    }
                }
            ],
            "values": [
                {"properties": {"fontSize": litteral("9D"), "fontColor": couleur(TEXTE), "wordWrap": litteral("false")}}
            ],
            "grid": [
                {
                    "properties": {
                        "gridVertical": litteral("false"),
                        "gridHorizontal": litteral("true"),
                        "gridHorizontalColor": couleur("#E1DFDD"),
                    }
                }
            ],
            "total": [{"properties": {"totals": litteral("false")}}],
        },
        "visualContainerObjects": conteneur(spec["titre"], spec["titre"]),
    }


def filtre_rang(nom_mesure: str, nom_visuel: str) -> dict:
    def borne(genre: int, valeur: int) -> dict:
        return {
            "Comparison": {
                "ComparisonKind": genre,
                "Left": mesure(nom_mesure, "m"),
                "Right": {"Literal": {"Value": f"{valeur}D"}},
            }
        }

    return {
        "name": "Filter" + identifiant(nom_visuel, nom_mesure)[:20],
        "field": mesure(nom_mesure),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "m", "Entity": "Mesures", "Type": 0}],
            "Where": [{"Condition": {"And": {"Left": borne(2, 1), "Right": borne(4, RANG_MAX)}}}],
        },
        "howCreated": "User",
    }


def filtre_exclusion(table: str, nom_colonne: str, valeur: str, nom_visuel: str) -> dict:
    return {
        "name": "Filter" + identifiant(nom_visuel, nom_colonne)[:20],
        "field": colonne(table, nom_colonne),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "d", "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Not": {
                            "Expression": {
                                "In": {
                                    "Expressions": [colonne(table, nom_colonne, "d")],
                                    "Values": [[{"Literal": {"Value": f"'{valeur}'"}}]],
                                }
                            }
                        }
                    }
                }
            ],
        },
        "howCreated": "User",
    }


# --------------------------------------------------------------------------- pages
def construire_page(index: int, page: dict) -> tuple[str, dict, list[dict]]:
    nom_page = identifiant("page", str(index))
    visuels = []
    ordre = 1000

    def ajouter(cle: str, rect, visuel, filtres=None):
        nonlocal ordre
        visuels.append(enveloppe(identifiant(nom_page, cle), rect, ordre, visuel, filtres))
        ordre += 1000

    ajouter("titre", TITRE, carte_texte(page["titre"], 14, TEXTE, None, fond=False))
    ajouter("synthese", SYNTHESE, carte_texte(page["synthese"], 10, TEXTE, None, fond=False))
    ajouter("segment_annee", SEGMENT_ANNEE, segment("dim_date", "year", "Année", 2026))
    ajouter("segment_region", SEGMENT_REGION, segment("dim_store", "region", "Région", None))
    for i, (libelle, valeur, detail) in enumerate(page["cartes"]):
        x = CARTES_X[i]
        ajouter(
            f"carte{i}",
            (x, CARTE_VALEUR_Y, LARGEUR_CARTE, CARTE_VALEUR_H),
            carte_texte(valeur, 14, TEXTE, libelle, True),
        )
        ajouter(
            f"detail{i}",
            (x, CARTE_DETAIL_Y, LARGEUR_CARTE, CARTE_DETAIL_H),
            carte_texte(detail, 10, TEXTE_SECONDAIRE, None, True),
        )
    for spec in page["visuels"]:
        cle = spec["zone"]
        nom_visuel = identifiant(nom_page, cle)
        filtres = []
        if spec["type"] == "barres":
            visuel = barres(spec)
            if spec.get("exclure"):
                filtres.append(filtre_exclusion(*spec["exclure"], nom_visuel))
        elif spec["type"] == "colonnes":
            visuel = colonnes_mensuelles(spec)
        else:
            visuel = tableau(spec)
            if spec["rang"]:
                filtres.append(filtre_rang(spec["rang"], nom_visuel))
        ajouter(cle, ZONES[cle], visuel, filtres or None)

    definition = {
        "$schema": f"{SCHEMA}/page/2.1.0/schema.json",
        "name": nom_page,
        "displayName": page["nom"],
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
        "objects": {
            "background": [{"properties": {"color": couleur(FOND), "transparency": litteral("0D")}}],
            "displayArea": [{"properties": {"verticalAlignment": litteral("'Middle'")}}],
        },
    }
    return nom_page, definition, visuels


def rapport() -> dict:
    version = {"visual": "2.11.0", "report": "3.4.0", "page": "2.3.1"}
    return {
        "$schema": f"{SCHEMA}/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": BASE_THEME, "reportVersionAtImport": version, "type": "SharedResources"},
            "customTheme": {"name": THEME, "reportVersionAtImport": version, "type": "RegisteredResources"},
        },
        "objects": {"outspacePane": [{"properties": {"visible": litteral("false")}}]},
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}],
            },
            {
                "name": "RegisteredResources",
                "type": "RegisteredResources",
                "items": [{"name": THEME, "path": THEME, "type": "CustomTheme"}],
            },
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
            "defaultFilterActionIsDataFilter": True,
            "hideVisualContainerHeader": True,
        },
    }


def ecrire(chemin: Path, contenu: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    dossier_pages = RAPPORT / "pages"
    if dossier_pages.exists():
        shutil.rmtree(dossier_pages)
    ecrire(RAPPORT / "report.json", rapport())
    ecrire(
        RAPPORT / "version.json",
        {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    noms = []
    total = 0
    for index, page in enumerate(PAGES):
        nom_page, definition, visuels = construire_page(index, page)
        noms.append(nom_page)
        ecrire(dossier_pages / nom_page / "page.json", definition)
        for visuel in visuels:
            ecrire(dossier_pages / nom_page / "visuals" / visuel["name"] / "visual.json", visuel)
        total += len(visuels)
    ecrire(
        dossier_pages / "pages.json",
        {"$schema": f"{SCHEMA}/pagesMetadata/1.1.0/schema.json", "pageOrder": noms, "activePageName": noms[0]},
    )
    print(f"Rapport : {len(noms)} pages, {total} visuels écrits dans {RAPPORT.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
