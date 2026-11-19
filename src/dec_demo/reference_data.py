"""Static reference data for the fictitious DIY retailer.

Everything here is invented. City names are used only as generic locations;
no real retailer, brand or person is represented.
"""

from __future__ import annotations

# Region code -> cities hosting a store. Unequal sizes on purpose (no flat distribution).
STORES_BY_REGION: dict[str, list[str]] = {
    "IDF": ["Créteil", "Nanterre", "Cergy", "Évry", "Versailles", "Saint-Denis", "Meaux", "Massy"],
    "NORD": ["Lille", "Roubaix", "Valenciennes", "Arras", "Amiens", "Dunkerque", "Lens"],
    "EST": ["Metz", "Nancy", "Strasbourg", "Reims", "Mulhouse", "Dijon"],
    "OUEST": ["Nantes", "Rennes", "Angers", "Le Mans", "Brest", "Tours", "Caen"],
    "SUD_EST": ["Lyon", "Marseille", "Nice", "Grenoble", "Montpellier", "Toulon", "Saint-Étienne"],
    "SUD_OUEST": ["Bordeaux", "Toulouse", "Pau", "Bayonne", "Limoges"],
}

# Product families: (catalog share, median list price EUR, price log-sigma, gross margin rate,
#                    quantity multiplier, sub-families)
FAMILIES: dict[str, tuple[float, float, float, float, float, list[str]]] = {
    "Outillage": (0.16, 35.0, 0.9, 0.38, 1.0, ["Outillage électroportatif", "Outillage à main", "Mesure et traçage"]),
    "Matériaux": (0.14, 18.0, 0.9, 0.24, 3.0, ["Gros œuvre", "Isolation", "Plaques de plâtre", "Bois de construction"]),
    "Peinture": (
        0.11,
        28.0,
        0.6,
        0.42,
        1.5,
        ["Peinture intérieure", "Peinture extérieure", "Préparation des surfaces"],
    ),
    "Plomberie": (0.12, 14.0, 0.8, 0.40, 1.8, ["Raccords", "Tuyauterie", "Robinetterie"]),
    "Électricité": (0.13, 12.0, 0.8, 0.41, 2.0, ["Câbles", "Appareillage", "Éclairage"]),
    "Jardin": (
        0.12,
        26.0,
        1.0,
        0.36,
        1.4,
        ["Outils de jardin", "Arrosage", "Mobilier de jardin", "Terreau et engrais"],
    ),
    "Menuiserie": (0.10, 45.0, 0.9, 0.33, 1.2, ["Portes et fenêtres", "Parquet et sols", "Quincaillerie"]),
    "Sanitaire": (0.12, 90.0, 0.8, 0.35, 1.0, ["Salle de bain", "WC", "Chauffe-eau"]),
}

# Invented house-style brand names (no real brand).
BRANDS: list[str] = [
    "Atelix",
    "Bativo",
    "Pigmenta",
    "Hydrel",
    "Voltix",
    "Jardéo",
    "Boisane",
    "Sanilo",
    "Fortis",
    "Nuvia",
]

PRODUCT_QUALIFIERS: list[str] = ["Standard", "Pro", "Compact", "Premium", "Éco", "XL", "Confort", "Essentiel"]

FIRST_NAMES: list[str] = [
    "Camille",
    "Léa",
    "Manon",
    "Chloé",
    "Emma",
    "Inès",
    "Sarah",
    "Julie",
    "Laura",
    "Clara",
    "Pauline",
    "Marie",
    "Anaïs",
    "Lucie",
    "Nadia",
    "Sophie",
    "Élodie",
    "Amandine",
    "Yasmine",
    "Céline",
    "Lucas",
    "Hugo",
    "Thomas",
    "Nicolas",
    "Julien",
    "Maxime",
    "Antoine",
    "Kevin",
    "Mehdi",
    "Romain",
    "Alexandre",
    "Quentin",
    "Mathieu",
    "Florian",
    "Karim",
    "Sébastien",
    "Vincent",
    "Olivier",
    "Pierre",
    "Yanis",
]

LAST_NAMES: list[str] = [
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Simon",
    "Laurent",
    "Lefèvre",
    "Michel",
    "Garcia",
    "David",
    "Bertrand",
    "Roux",
    "Vincent",
    "Fournier",
    "Morel",
    "Girard",
    "André",
    "Lefebvre",
    "Mercier",
    "Dupont",
    "Lambert",
    "Bonnet",
    "François",
    "Martinez",
    "Legrand",
    "Garnier",
    "Faure",
    "Rousseau",
    "Blanc",
    "Guerin",
    "Muller",
    "Henry",
    "Roussel",
    "Nicolas",
    "Perrin",
    "Morin",
    "Mathieu",
    "Clément",
    "Gauthier",
    "Dumont",
    "Lopez",
    "Fontaine",
    "Chevalier",
    "Robin",
]

# Calendar of the demo history.
HISTORY_START = "2024-11-01"
HISTORY_END = "2026-10-31"

# Business incident: supplier delay -> stockout on top garden SKUs in NORD stores.
STOCKOUT_REGION = "NORD"
STOCKOUT_FAMILY = "Jardin"
STOCKOUT_TOP_SKUS = 60
STOCKOUT_START = "2026-04-06"
STOCKOUT_END = "2026-05-17"

# Data incident: one store's POS export sends prices in cents instead of euros for one day.
PRICE_INCIDENT_CITY = "Metz"
PRICE_INCIDENT_DATE = "2026-10-14"
