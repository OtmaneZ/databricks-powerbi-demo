"""Fichiers Parquet de powerbi/data/ : cohérence avec le manifeste, taille, données personnelles,
et correspondance avec les partitions du modèle TMDL."""

import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import tmdl

DONNEES = tmdl.RACINE / "powerbi" / "data"
MANIFESTE = json.loads((DONNEES / "manifest.json").read_text(encoding="utf-8"))
LIMITE_GITHUB = 50 * 1024 * 1024
COLONNES_PERSONNELLES = {"first_name", "last_name", "email", "phone"}

# Types TMDL acceptés pour chaque famille de types Parquet.
TYPES_COMPATIBLES = {
    "string": lambda t: pa.types.is_string(t) or pa.types.is_large_string(t),
    "int64": pa.types.is_integer,
    "decimal": lambda t: pa.types.is_decimal(t) or pa.types.is_floating(t),
    "dateTime": lambda t: pa.types.is_date(t) or pa.types.is_timestamp(t),
    "boolean": pa.types.is_boolean,
}


def test_manifeste_couvre_tous_les_fichiers():
    assert set(MANIFESTE) == {p.name for p in DONNEES.glob("*.parquet")}


@pytest.mark.parametrize("nom", sorted(MANIFESTE))
def test_fichier_conforme_au_manifeste(nom):
    chemin = DONNEES / nom
    assert pq.ParquetFile(chemin).metadata.num_rows == MANIFESTE[nom]["rows"]
    assert chemin.stat().st_size == MANIFESTE[nom]["bytes"]
    assert chemin.stat().st_size < LIMITE_GITHUB


@pytest.mark.parametrize("nom", sorted(MANIFESTE))
def test_aucune_donnee_personnelle(nom):
    colonnes = set(pq.read_schema(DONNEES / nom).names)
    assert not colonnes & COLONNES_PERSONNELLES
    if nom == "dim_customer.parquet":
        assert colonnes == {"customer_id", "customer_segment", "home_store_id", "loyalty_since", "marketing_optin"}


def _partitions_parquet():
    for nom, table in tmdl.lire_modele().tables.items():
        for partition in table.enfants_de_type("partition"):
            source = partition.proprietes.get("source", "")
            fichier = re.search(r'DossierDonnees & "([^"]+\.parquet)"', source)
            if fichier:
                yield nom, table, fichier.group(1), source


def test_chaque_table_importee_a_son_fichier():
    attendues = {
        "fct_sales",
        "fct_stock_weekly",
        "quarantine_sales",
        "dim_date",
        "dim_store",
        "dim_product",
        "dim_customer",
        "security_region_access",
    }
    trouvees = {nom for nom, _, fichier, _ in _partitions_parquet() if (DONNEES / fichier).exists()}
    assert trouvees == attendues


@pytest.mark.parametrize(
    "nom,table,fichier,source",
    list(_partitions_parquet()),
    ids=lambda v: v if isinstance(v, str) and v.endswith(".parquet") else "",
)
def test_colonnes_du_modele_presentes_dans_le_parquet(nom, table, fichier, source):
    schema = pq.read_schema(DONNEES / fichier)
    selection = re.search(r"Table\.SelectColumns\(Source, \{([^}]*)\}\)", source)
    assert selection, f"{nom} : pas de Table.SelectColumns"
    colonnes_lues = re.findall(r'"([^"]+)"', selection.group(1))
    assert set(colonnes_lues) <= set(schema.names), f"{nom} : colonnes absentes du Parquet"
    derivees = {"quarantine_date", "reason_label"}
    for colonne in table.enfants_de_type("column"):
        source_colonne = colonne.proprietes["sourceColumn"]
        if source_colonne in derivees:
            continue
        assert source_colonne in colonnes_lues, f"{nom}[{colonne.nom}] non importée"
        type_parquet = schema.field(source_colonne).type
        assert TYPES_COMPATIBLES[colonne.proprietes["dataType"]](type_parquet), (
            f"{nom}[{colonne.nom}] : {colonne.proprietes['dataType']} incompatible avec {type_parquet}"
        )


def test_parametre_dossier_par_defaut():
    expression = tmdl.lire_modele().expressions[0]
    assert expression.nom == "DossierDonnees"
    assert expression.valeur.startswith('"C:\\databricks-powerbi-demo\\powerbi\\data\\"')


def test_dossier_exporte_par_le_script():
    from dec_demo import export_gold

    assert Path(export_gold.OUTPUT_DIR) == DONNEES
    assert {f"{nom.split('.')[1]}.parquet" for nom, _ in export_gold.EXPORTS} == set(MANIFESTE)
