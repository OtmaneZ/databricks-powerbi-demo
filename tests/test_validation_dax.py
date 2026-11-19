"""tests/validation.dax est à jour et ne cite que des mesures et des filtres du modèle."""

import json

import build_validation_dax
import tmdl


def test_validation_dax_a_jour():
    assert build_validation_dax.FICHIER_DAX.read_text(encoding="utf-8") == build_validation_dax.construire()


def test_mesures_et_filtres_connus():
    mesures = {mesure.nom for _, mesure in tmdl.lire_modele().mesures()}
    for fichier in sorted(build_validation_dax.DOSSIER_ATTENDUS.glob("*.json")):
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        assert set(contenu["filtres"]) <= set(build_validation_dax.FILTRES_DAX), fichier.name
        for ligne in contenu["mesures"]:
            assert ligne["mesure"] in mesures, f"{fichier.name} : {ligne['mesure']}"
            assert ligne["type"] in (*build_validation_dax.TOLERANCES, "texte")


def test_cas_couverts():
    cas = {
        json.loads(f.read_text(encoding="utf-8"))["cas"] for f in build_validation_dax.DOSSIER_ATTENDUS.glob("*.json")
    }
    assert {"2026 total", "2026 région NORD", "2026 NORD Jardin avril", "2026 Magasin Metz octobre"} <= cas
